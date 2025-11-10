"""Qdrant database adapter for hexagonal architecture."""

import logging
import requests
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional, Tuple

from ...constants import DEFAULT_MAX_WORKERS, DEFAULT_VECTOR_SIZE
from ...rate_limiter import db_rate_limiter
from ...validation import validate_collection_name, validate_distance_metric
from ..port import (
    VectorDatabase,
    CollectionNotFoundError,
    DatabaseConnectionError,
    DatabaseTimeoutError,
    DatabaseOperationError,
    InvalidCollectionNameError,
    InvalidVectorSizeError,
)
from .. import register_adapter

logger = logging.getLogger(__name__)


def _create_qdrant_adapter(qdrant_url: Optional[str] = None) -> "QdrantVectorDatabase":
    """
    Create a QdrantVectorDatabase instance.

    Factory function registered with the adapter registry to enable pluggable architecture.

    Args:
        qdrant_url: Optional Qdrant URL. If None, uses config default.

    Returns:
        QdrantVectorDatabase instance
    """
    return QdrantVectorDatabase(qdrant_url=qdrant_url)


class QdrantError(Exception):
    """Base exception for Qdrant adapter errors."""

    pass


class QdrantCollectionNotFoundError(CollectionNotFoundError, QdrantError):
    """Exception raised when a collection is not found in Qdrant."""

    pass


class QdrantNetworkError(QdrantError):
    """Exception raised for network-related errors."""

    pass


class QdrantVectorDatabase(VectorDatabase):
    """Qdrant implementation of VectorDatabase port."""

    def __init__(self, qdrant_url: Optional[str] = None):
        """
        Initialize Qdrant vector database client.

        Args:
            qdrant_url: Base URL for Qdrant instance (defaults to config value)
        """
        from ...config import get_config

        if qdrant_url is None:
            config = get_config()
            qdrant_url = config.qdrant_url

        self.qdrant_url = qdrant_url.rstrip("/")
        self._hybrid_collections_cache: Dict[str, bool] = {}

    def _make_request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Tuple[requests.Response, bool]:
        """
        Make an HTTP request with proper error handling and rate limiting.

        Args:
            method: HTTP method (get, post, put, delete)
            url: Request URL
            json: Optional JSON payload
            timeout: Request timeout in seconds

        Returns:
            Tuple of (response object, success boolean)

        Raises:
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
        """
        # Apply rate limiting before making request
        db_rate_limiter.acquire()

        try:
            method_func = getattr(requests, method.lower())
            if json is not None:
                resp = method_func(url, json=json, timeout=timeout)
            else:
                resp = method_func(url, timeout=timeout)
            return resp, True
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout for {method} {url}: {e}")
            raise DatabaseTimeoutError(
                f"Connection timeout: Unable to reach Qdrant at {self.qdrant_url}. "
                f"Please check that Qdrant is running and accessible."
            ) from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error for {method} {url}: {e}")
            raise DatabaseConnectionError(
                f"Connection failed: Unable to connect to Qdrant at {self.qdrant_url}. "
                f"Please check that Qdrant is running and the URL is correct."
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {method} {url}: {e}")
            raise DatabaseOperationError(
                f"Request failed: Error communicating with Qdrant at {self.qdrant_url}. "
                f"Error: {e}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error for {method} {url}: {e}")
            raise DatabaseOperationError(
                f"Unexpected error communicating with Qdrant at {self.qdrant_url}: {e}"
            ) from e

    def _collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.

        Args:
            collection_name: Name of the collection to check

        Returns:
            True if collection exists, False otherwise
        """
        try:
            url = f"{self.qdrant_url}/collections/{collection_name}"
            resp, _ = self._make_request("get", url)
            return resp.status_code == 200
        except (DatabaseConnectionError, DatabaseTimeoutError):
            # If we can't connect, assume it doesn't exist
            return False

    def create_collection(
        self,
        collection_name: str,
        distance_metric: str = "Cosine",
        vector_size: int = DEFAULT_VECTOR_SIZE,
        enable_hybrid: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new collection in Qdrant.

        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric (Cosine, Euclid, Dot)
            vector_size: Size of the dense vectors
            enable_hybrid: Enable hybrid search with sparse vectors

        Returns:
            Collection information

        Raises:
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
            ValueError: If collection already exists or validation fails
        """
        # Validate inputs
        validate_collection_name(collection_name)
        validate_distance_metric(distance_metric)

        # Check if collection already exists
        if self._collection_exists(collection_name):
            logger.info(
                f"Collection '{collection_name}' already exists. Returning existing collection info."
            )
            collection_info = self.get_collection_info(collection_name)
            # Cache hybrid status based on existing collection
            if collection_name not in self._hybrid_collections_cache:
                is_hybrid = self._detect_hybrid_from_info(collection_info)
                self._hybrid_collections_cache[collection_name] = is_hybrid
            return collection_info

        url = f"{self.qdrant_url}/collections/{collection_name}"

        if enable_hybrid:
            # Create collection with named vectors for hybrid search
            # dense: for semantic search
            # text: for keyword-based search (BM25) - matches MCP server expectation
            payload = {
                "vectors": {
                    "dense": {"size": vector_size, "distance": distance_metric}
                },
                "sparse_vectors": {"text": {}},  # Sparse vector configuration for BM25
            }
            logger.info(
                f"Creating collection '{collection_name}' with hybrid search enabled."
            )
        else:
            # Create standard collection with single dense vector
            payload = {"vectors": {"size": vector_size, "distance": distance_metric}}
            logger.info(
                f"Creating collection '{collection_name}' with semantic search only."
            )

        try:
            resp, _ = self._make_request("put", url, json=payload)
            if resp.status_code == 200:
                # Cache hybrid status for the new collection
                self._hybrid_collections_cache[collection_name] = enable_hybrid
                logger.debug(f"Created collection '{collection_name}'.")
                return resp.json()
            else:
                error_msg = (
                    f"Failed to create collection: {resp.status_code} — {resp.text}"
                )
                logger.error(error_msg)
                raise QdrantError(error_msg)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
            InvalidCollectionNameError,
            InvalidVectorSizeError,
            QdrantError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating collection: {e}")
            raise DatabaseOperationError(f"Failed to create collection: {e}") from e

    def delete_collection(self, collection_name: str) -> None:
        """
        Manually delete a Qdrant collection.

        Args:
            collection_name: Name of the collection to delete

        Raises:
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
            QdrantCollectionNotFoundError: If collection doesn't exist
            ValueError: If collection name is invalid
        """
        validate_collection_name(collection_name)
        url = f"{self.qdrant_url}/collections/{collection_name}"

        # Check if collection exists before deletion to provide better error messages
        # Qdrant's DELETE API is idempotent (returns 200 even for non-existent collections),
        # but we want to provide clear feedback to users
        collection_existed = self._collection_exists(collection_name)

        try:
            resp, _ = self._make_request("delete", url)
            if resp.status_code == 200:
                # Clear cache for deleted collection
                self._hybrid_collections_cache.pop(collection_name, None)
                # If collection didn't exist, raise error for user feedback
                if not collection_existed:
                    error_msg = f"Collection '{collection_name}' not found"
                    raise QdrantCollectionNotFoundError(error_msg)
            elif resp.status_code == 404:
                # Collection doesn't exist - raise explicit error
                self._hybrid_collections_cache.pop(collection_name, None)
                error_msg = f"Collection '{collection_name}' not found"
                raise QdrantCollectionNotFoundError(error_msg)
            else:
                error_msg = f"Failed to delete {collection_name}: {resp.status_code} — {resp.text}"
                logger.warning(error_msg)
                raise QdrantError(error_msg)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
            CollectionNotFoundError,
            InvalidCollectionNameError,
            QdrantError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting collection: {e}")
            raise DatabaseOperationError(f"Failed to delete collection: {e}") from e

    def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Delete all points from a collection without deleting the collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Operation result

        Raises:
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
            InvalidCollectionNameError: If collection name is invalid
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        url = f"{self.qdrant_url}/collections/{collection_name}/points/delete"
        try:
            resp, _ = self._make_request("post", url, json={"filter": {}})
            if resp.status_code == 200:
                logger.debug(f"Cleared all points from collection '{collection_name}'.")
                return resp.json()
            else:
                error_msg = f"Failed to clear collection '{collection_name}': {resp.status_code} — {resp.text}"
                logger.warning(error_msg)
                raise QdrantError(error_msg)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
            InvalidCollectionNameError,
            QdrantError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error clearing collection: {e}")
            raise DatabaseOperationError(f"Failed to clear collection: {e}") from e

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections in Qdrant.

        Returns:
            List of collection information

        Raises:
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
        """
        url = f"{self.qdrant_url}/collections"
        try:
            resp, _ = self._make_request("get", url)
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("collections", [])
            else:
                error_msg = (
                    f"Failed to list collections: {resp.status_code} — {resp.text}"
                )
                logger.warning(error_msg)
                raise DatabaseOperationError(error_msg)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing collections: {e}")
            raise DatabaseOperationError(f"Failed to list collections: {e}") from e

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection in Qdrant.

        Args:
            collection_name: Name of the collection

        Returns:
            Collection information

        Raises:
            CollectionNotFoundError: If collection doesn't exist
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
            InvalidCollectionNameError: If collection name is invalid
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        url = f"{self.qdrant_url}/collections/{collection_name}"
        try:
            resp, _ = self._make_request("get", url)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                # Collection doesn't exist - raise explicit error
                error_msg = f"Collection '{collection_name}' not found"
                logger.debug(error_msg)
                raise QdrantCollectionNotFoundError(error_msg)
            else:
                error_msg = (
                    f"Failed to get collection info: {resp.status_code} — {resp.text}"
                )
                logger.warning(error_msg)
                raise QdrantError(error_msg)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
            CollectionNotFoundError,
            InvalidCollectionNameError,
            QdrantError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting collection info: {e}")
            raise DatabaseOperationError(f"Failed to get collection info: {e}") from e

    def _generate_point_id(self, file_name: str, chunk_id: int) -> str:
        """
        Generate deterministic UUID from file name and chunk ID.

        Args:
            file_name: Source file name
            chunk_id: Chunk identifier

        Returns:
            UUID string
        """
        base_hash = hashlib.sha256(f"{file_name}-{chunk_id}".encode()).hexdigest()[:32]
        return str(uuid.UUID(base_hash))

    def _generate_collision_point_id(
        self, file_name: str, chunk_id: int, chunk_text: str
    ) -> str:
        """
        Generate fallback UUID for hash collision scenarios.

        Args:
            file_name: Source file name
            chunk_id: Chunk identifier
            chunk_text: Chunk text content

        Returns:
            UUID string
        """
        content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()[:16]
        collision_hash = hashlib.sha256(
            f"{file_name}-{chunk_id}-{content_hash}".encode()
        ).hexdigest()[:32]
        return str(uuid.UUID(collision_hash))

    def _check_point_exists(
        self, collection: str, point_id: str, file_name: str, chunk_id: int
    ) -> Tuple[bool, bool]:
        """
        Check if a point exists and verify it matches expected content.

        Args:
            collection: Collection name
            point_id: Point ID to check
            file_name: Expected file name
            chunk_id: Expected chunk ID

        Returns:
            Tuple of (exists, is_match) where:
            - exists: True if point exists
            - is_match: True if point exists and matches expected content

        Raises:
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
        """
        check_url = f"{self.qdrant_url}/collections/{collection}/points/{point_id}"
        try:
            check_resp, _ = self._make_request("get", check_url)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
            logger.error(f"Network error checking point existence: {e}")
            raise

        if check_resp.status_code != 200:
            return False, False

        # Point exists - verify it's the same content
        existing_point = check_resp.json().get("result", {})
        existing_payload = existing_point.get("payload", {})

        is_match = (
            existing_payload.get("source_file") == file_name
            and existing_payload.get("chunk_id") == chunk_id
        )
        return True, is_match

    def _ensure_hybrid_collection_cached(self, collection: str) -> bool:
        """
        Ensure hybrid collection status is cached, fetching if needed.

        Args:
            collection: Collection name

        Returns:
            True if collection is hybrid, False otherwise
        """
        if collection in self._hybrid_collections_cache:
            return self._hybrid_collections_cache[collection]

        try:
            collection_info = self.get_collection_info(collection)
            is_hybrid = self._detect_hybrid_from_info(collection_info)
            self._hybrid_collections_cache[collection] = is_hybrid
            logger.info(
                f"Collection '{collection}' detected as {'hybrid' if is_hybrid else 'standard'} collection."
            )
            return is_hybrid
        except (
            QdrantError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
            logger.error(
                f"Failed to detect hybrid status for collection '{collection}': {e}. "
                f"Assuming standard collection."
            )
            is_hybrid = False
            self._hybrid_collections_cache[collection] = is_hybrid
            return is_hybrid

    def _format_vector_payload(self, vector: List[float], is_hybrid: bool) -> Any:
        """
        Format vector payload based on collection type.

        Args:
            vector: Embedding vector
            is_hybrid: Whether collection uses hybrid search

        Returns:
            Formatted vector payload
        """
        if is_hybrid:
            return {"dense": vector}
        return vector

    def _create_point_payload(
        self,
        point_id: str,
        vector: List[float],
        chunk_text: str,
        file_name: str,
        chunk_id: int,
        is_hybrid: bool,
    ) -> Dict[str, Any]:
        """
        Create a point payload for upload.

        Args:
            point_id: Point UUID
            vector: Embedding vector
            chunk_text: Chunk text content
            file_name: Source file name
            chunk_id: Chunk identifier
            is_hybrid: Whether collection uses hybrid search

        Returns:
            Point payload dictionary
        """
        vector_payload = self._format_vector_payload(vector, is_hybrid)
        payload = {
            "chunk_text": chunk_text,
            "source_file": file_name,
            "chunk_id": chunk_id,
        }
        return {
            "id": point_id,
            "vector": vector_payload,
            "payload": payload,
        }

    def _detect_hybrid_from_info(self, collection_info: Dict[str, Any]) -> bool:
        """
        Detect if a collection is hybrid from its info structure.

        Args:
            collection_info: Collection information dictionary

        Returns:
            True if collection is hybrid, False otherwise

        Raises:
            ValueError: If collection info structure is invalid
        """
        try:
            # Collection info structure: {"result": {"config": {"params": {...}}}}
            if not isinstance(collection_info, dict):
                raise ValueError("Collection info must be a dictionary")

            result = collection_info.get("result", {})
            if not isinstance(result, dict):
                logger.warning(
                    "Collection info missing 'result' key or not a dict. Assuming standard collection."
                )
                return False

            config = result.get("config", {})
            if not isinstance(config, dict):
                logger.warning(
                    "Collection info missing 'config' key or not a dict. Assuming standard collection."
                )
                return False

            params = config.get("params", {})
            if not isinstance(params, dict):
                logger.warning(
                    "Collection info missing 'params' key or not a dict. Assuming standard collection."
                )
                return False

            # Check for sparse_vectors (indicates hybrid)
            has_sparse = bool(params.get("sparse_vectors"))

            # Check if vectors is a dict with named vectors (indicates hybrid)
            # Standard: {"size": <DEFAULT_VECTOR_SIZE>, "distance": "Cosine"}
            # Hybrid: {"dense": {"size": <DEFAULT_VECTOR_SIZE>, "distance": "Cosine"}}
            vectors_config = params.get("vectors", {})
            has_named_vectors = (
                isinstance(vectors_config, dict)
                and "dense" in vectors_config  # Explicit check for "dense" named vector
            )

            is_hybrid = has_sparse or has_named_vectors
            logger.debug(
                f"Hybrid detection: sparse_vectors={has_sparse}, "
                f"named_vectors={has_named_vectors}, is_hybrid={is_hybrid}"
            )
            return is_hybrid
        except Exception as e:
            logger.error(
                f"Error detecting hybrid collection: {e}. Assuming standard collection."
            )
            return False

    def upload_chunk(
        self,
        collection: str,
        chunk_text: str,
        file_name: str,
        chunk_id: int,
        embedding_func: Callable[[str], List[float]],
    ) -> None:
        """
        Upload one chunk to Qdrant if it doesn't already exist.

        Args:
            collection: Collection name
            chunk_text: Text content of the chunk
            file_name: Source file name
            chunk_id: Chunk identifier
            embedding_func: Function to generate embeddings (takes text, returns vector)

        Raises:
            ValueError: If collection name is invalid
        """
        try:
            validate_collection_name(collection)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        # Generate point ID and check if it already exists
        point_id = self._generate_point_id(file_name, chunk_id)
        exists, is_match = self._check_point_exists(
            collection, point_id, file_name, chunk_id
        )

        if exists and is_match:
            logger.debug(f"Skipping existing chunk {file_name}-{chunk_id}")
            return

        if exists and not is_match:
            # Hash collision detected - use fallback UUID generation
            logger.warning(
                f"Hash collision detected for {file_name}-{chunk_id}. "
                f"Existing point has different content. Using fallback UUID."
            )
            point_id = self._generate_collision_point_id(
                file_name, chunk_id, chunk_text
            )

            # Re-check with fallback ID
            exists, is_match = self._check_point_exists(
                collection, point_id, file_name, chunk_id
            )
            if exists:
                # Even the fallback collided (extremely unlikely), log and skip
                logger.error(
                    f"Fallback UUID also exists for {file_name}-{chunk_id}. Skipping upload."
                )
                return

        # Generate embedding and prepare point
        vector = embedding_func(chunk_text)
        is_hybrid = self._ensure_hybrid_collection_cached(collection)
        point = self._create_point_payload(
            point_id, vector, chunk_text, file_name, chunk_id, is_hybrid
        )

        data = {"points": [point]}
        upload_url = f"{self.qdrant_url}/collections/{collection}/points?wait=true"
        try:
            resp, _ = self._make_request("put", upload_url, json=data)
            if not resp.ok:
                error_msg = f"Upload failed for {file_name}-{chunk_id}: {resp.status_code} — {resp.text}"
                logger.error(error_msg)
                raise QdrantError(error_msg)
            else:
                logger.info(f"Uploaded chunk {file_name}-{chunk_id}")
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
            InvalidCollectionNameError,
            QdrantError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading chunk: {e}")
            raise DatabaseOperationError(f"Failed to upload chunk: {e}") from e

    def _prepare_points_parallel(
        self,
        chunks: List[Tuple[str, str, int]],
        embedding_func: Callable[[str], List[float]],
        is_hybrid: bool,
        max_workers: int,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Prepare points in parallel using ThreadPoolExecutor.

        Args:
            chunks: List of tuples (chunk_text, file_name, chunk_id)
            embedding_func: Function to generate embeddings
            is_hybrid: Whether collection is hybrid
            max_workers: Maximum number of parallel workers

        Returns:
            List of prepared point payloads
        """
        points = []

        def prepare_point(
            chunk_text: str, file_name: str, chunk_id: int
        ) -> Dict[str, Any]:
            """Prepare a single point with embedding."""
            point_id = self._generate_point_id(file_name, chunk_id)
            vector = embedding_func(chunk_text)
            return self._create_point_payload(
                point_id, vector, chunk_text, file_name, chunk_id, is_hybrid
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(prepare_point, chunk_text, file_name, chunk_id): (
                    chunk_text,
                    file_name,
                    chunk_id,
                )
                for chunk_text, file_name, chunk_id in chunks
            }

            for future in as_completed(future_to_chunk):
                try:
                    point = future.result()
                    points.append(point)
                    if progress_callback:
                        progress_callback(1)
                except Exception as e:
                    chunk_text, file_name, chunk_id = future_to_chunk[future]
                    logger.error(
                        f"Failed to prepare point for {file_name}-{chunk_id}: {e}"
                    )
                    # Continue with other points even if one fails
                    if progress_callback:
                        progress_callback(1)  # Still count failed chunks

        return points

    def _prepare_points_sequential(
        self,
        chunks: List[Tuple[str, str, int]],
        embedding_func: Callable[[str], List[float]],
        is_hybrid: bool,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Prepare points sequentially.

        Args:
            chunks: List of tuples (chunk_text, file_name, chunk_id)
            embedding_func: Function to generate embeddings
            is_hybrid: Whether collection is hybrid

        Returns:
            List of prepared point payloads
        """
        points = []

        def prepare_point(
            chunk_text: str, file_name: str, chunk_id: int
        ) -> Dict[str, Any]:
            """Prepare a single point with embedding."""
            point_id = self._generate_point_id(file_name, chunk_id)
            vector = embedding_func(chunk_text)
            return self._create_point_payload(
                point_id, vector, chunk_text, file_name, chunk_id, is_hybrid
            )

        for chunk_text, file_name, chunk_id in chunks:
            try:
                point = prepare_point(chunk_text, file_name, chunk_id)
                points.append(point)
                if progress_callback:
                    progress_callback(1)
            except Exception as e:
                logger.error(f"Failed to prepare point for {file_name}-{chunk_id}: {e}")
                if progress_callback:
                    progress_callback(1)  # Still count failed chunks

        return points

    def _upload_batch_points(
        self, collection: str, points: List[Dict[str, Any]], num_chunks: int
    ) -> None:
        """
        Upload prepared points to Qdrant.

        Args:
            collection: Collection name
            points: List of prepared point payloads
            num_chunks: Number of chunks being uploaded (for error messages)

        Raises:
            QdrantError: If batch upload fails
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
        """
        data = {"points": points}
        upload_url = f"{self.qdrant_url}/collections/{collection}/points?wait=true"
        try:
            resp, _ = self._make_request("put", upload_url, json=data)
            if not resp.ok:
                error_msg = (
                    f"Batch upload failed for {num_chunks} chunks: "
                    f"{resp.status_code} — {resp.text}"
                )
                logger.error(error_msg)
                raise QdrantError(error_msg)
            else:
                logger.debug(f"Successfully uploaded batch of {num_chunks} chunks")
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
            InvalidCollectionNameError,
            QdrantError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in batch upload: {e}")
            raise DatabaseOperationError(f"Failed to upload batch: {e}") from e

    def upload_chunks_batch(
        self,
        collection: str,
        chunks: List[Tuple[str, str, int]],
        embedding_func: Callable[[str], List[float]],
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Upload multiple chunks in a single batch operation for better performance.

        Args:
            collection: Collection name
            chunks: List of tuples (chunk_text, file_name, chunk_id)
            embedding_func: Function to generate embeddings (takes text, returns vector)
            progress_callback: Optional callback function called with number of processed chunks

        Raises:
            QdrantError: If batch upload fails
            DatabaseConnectionError: If unable to connect to Qdrant
            DatabaseTimeoutError: If request times out
            DatabaseOperationError: If operation fails
            ValueError: If collection name is invalid
        """
        try:
            validate_collection_name(collection)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        if not chunks:
            return

        # Ensure hybrid collection status is cached
        is_hybrid = self._ensure_hybrid_collection_cached(collection)

        # Determine processing strategy
        max_workers = min(DEFAULT_MAX_WORKERS, len(chunks))
        use_parallel = max_workers > 1 and len(chunks) > 1

        # Prepare points
        if use_parallel:
            points = self._prepare_points_parallel(
                chunks, embedding_func, is_hybrid, max_workers, progress_callback
            )
        else:
            points = self._prepare_points_sequential(
                chunks, embedding_func, is_hybrid, progress_callback
            )

        # Upload batch
        self._upload_batch_points(collection, points, len(chunks))

    def search(
        self, collection_name: str, vector: List[float], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in Qdrant collection.

        Args:
            collection_name: Name of the collection to search
            vector: Query vector
            limit: Maximum number of results

        Returns:
            List of search results with score and payload

        Raises:
            ValueError: If collection name is invalid
        """
        validate_collection_name(collection_name)
        search_url = f"{self.qdrant_url}/collections/{collection_name}/points/search"
        search_data = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }

        try:
            resp, _ = self._make_request("post", search_url, json=search_data)
            if resp.status_code == 200:
                results = resp.json().get("result", [])
                return results
            else:
                error_msg = f"Failed to search: {resp.status_code} — {resp.text}"
                logger.warning(error_msg)
                raise QdrantError(error_msg)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
            InvalidCollectionNameError,
            QdrantError,
        ):
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching: {e}")
            raise DatabaseOperationError(f"Failed to search: {e}") from e


# Register the Qdrant adapter with the registry
# This makes it available via create_vector_database("qdrant", ...)
register_adapter("qdrant", _create_qdrant_adapter)
