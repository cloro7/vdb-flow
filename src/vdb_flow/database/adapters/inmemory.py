"""In-memory vector database adapter for testing and development."""

import logging
from typing import List, Dict, Any, Callable, Optional
from collections import defaultdict

from ...constants import DEFAULT_VECTOR_SIZE
from ...validation import validate_collection_name, validate_distance_metric
from ..port import (
    VectorDatabase,
    InvalidCollectionNameError,
    CollectionNotFoundError,
    InvalidVectorSizeError,
    DatabaseOperationError,
)
from .. import register_adapter

logger = logging.getLogger(__name__)


def _create_inmemory_adapter(**kwargs) -> "InMemoryVectorDatabase":
    """
    Create an InMemoryVectorDatabase instance.

    Factory function registered with the adapter registry to enable pluggable architecture.

    Args:
        **kwargs: Ignored (for compatibility with other adapters)

    Returns:
        InMemoryVectorDatabase instance
    """
    return InMemoryVectorDatabase()


class InMemoryVectorDatabase(VectorDatabase):
    """
    In-memory vector database adapter for testing and development.

    Stores collections and points in memory using Python data structures.
    This adapter is useful for:
    - Testing without external dependencies
    - Development and prototyping
    - Demonstrating the pluggable architecture

    Note: Data is not persisted and will be lost when the process exits.
    """

    def __init__(self):
        """Initialize the in-memory database."""
        # Structure: {collection_name: {"config": {...}, "points": {point_id: {...}}}}
        self._collections: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"config": {}, "points": {}}
        )

    def create_collection(
        self,
        collection_name: str,
        distance_metric: str = "Cosine",
        vector_size: int = DEFAULT_VECTOR_SIZE,
        enable_hybrid: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new collection in memory.

        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric (Cosine, Euclid, Dot)
            vector_size: Size of the dense vectors
            enable_hybrid: Enable hybrid search with sparse vectors (ignored in-memory)

        Returns:
            Collection information

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            InvalidVectorSizeError: If vector size is invalid
            CollectionAlreadyExistsError: If collection already exists
        """
        # Validate inputs
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        validate_distance_metric(distance_metric)

        if vector_size <= 0:
            raise InvalidVectorSizeError(
                f"Vector size must be positive, got {vector_size}"
            )

        # Check if collection already exists
        if (
            collection_name in self._collections
            and self._collections[collection_name]["points"]
        ):
            from ..port import CollectionAlreadyExistsError

            raise CollectionAlreadyExistsError(
                f"Collection '{collection_name}' already exists"
            )

        # Create collection
        self._collections[collection_name] = {
            "config": {
                "distance_metric": distance_metric,
                "vector_size": vector_size,
                "enable_hybrid": enable_hybrid,
            },
            "points": {},
        }

        logger.info(f"Created in-memory collection '{collection_name}'")
        return {
            "status": "ok",
            "result": {
                "vectors_count": 0,
                "indexed_vectors_count": 0,
                "points_count": 0,
                "config": {
                    "params": {
                        "vectors": {
                            "size": vector_size,
                            "distance": distance_metric,
                        }
                    }
                },
            },
        }

    def delete_collection(self, collection_name: str) -> None:
        """
        Delete a collection from memory.

        Args:
            collection_name: Name of the collection to delete

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            CollectionNotFoundError: If collection doesn't exist
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        if collection_name not in self._collections:
            raise CollectionNotFoundError(f"Collection '{collection_name}' not found")

        del self._collections[collection_name]
        logger.info(f"Deleted in-memory collection '{collection_name}'")

    def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Clear all points from a collection without deleting it.

        Args:
            collection_name: Name of the collection

        Returns:
            Operation result

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            CollectionNotFoundError: If collection doesn't exist
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        if collection_name not in self._collections:
            raise CollectionNotFoundError(f"Collection '{collection_name}' not found")

        self._collections[collection_name]["points"].clear()
        logger.info(f"Cleared in-memory collection '{collection_name}'")
        return {"status": "ok", "result": {"operation_id": 0}}

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Collection information

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            CollectionNotFoundError: If collection doesn't exist
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        if collection_name not in self._collections:
            raise CollectionNotFoundError(f"Collection '{collection_name}' not found")

        collection = self._collections[collection_name]
        config = collection["config"]
        points_count = len(collection["points"])

        return {
            "status": "ok",
            "result": {
                "vectors_count": points_count,
                "indexed_vectors_count": points_count,
                "points_count": points_count,
                "config": {
                    "params": {
                        "vectors": {
                            "size": config["vector_size"],
                            "distance": config["distance_metric"],
                        }
                    }
                },
            },
        }

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections.

        Returns:
            List of collection information dictionaries
        """
        collections = []
        for name, collection in self._collections.items():
            points_count = len(collection["points"])
            collections.append(
                {
                    "name": name,
                    "points_count": points_count,
                    "vectors_count": points_count,
                }
            )
        return collections

    def upload_chunk(
        self,
        collection_name: str,
        chunk_text: str,
        file_name: str,
        chunk_id: int,
        embedding_func: Callable[[str], List[float]],
    ) -> None:
        """
        Upload a single chunk to a collection.

        Args:
            collection_name: Name of the collection
            chunk_text: Text content of the chunk
            file_name: Name of the source file
            chunk_id: Unique identifier for the chunk within the file
            embedding_func: Function to generate embeddings

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            CollectionNotFoundError: If collection doesn't exist
            DatabaseOperationError: If operation fails
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        if collection_name not in self._collections:
            raise CollectionNotFoundError(f"Collection '{collection_name}' not found")

        # Generate embedding
        vector = embedding_func(chunk_text)

        # Validate vector size matches collection config
        config = self._collections[collection_name]["config"]
        expected_size = config["vector_size"]
        if len(vector) != expected_size:
            raise DatabaseOperationError(
                f"Vector size mismatch: expected {expected_size}, got {len(vector)}"
            )

        # Generate deterministic point ID (similar to Qdrant adapter)
        import hashlib
        import uuid

        content_hash = hashlib.sha256(f"{file_name}-{chunk_id}".encode()).hexdigest()[
            :32
        ]
        point_id = str(uuid.UUID(content_hash))

        # Store point
        self._collections[collection_name]["points"][point_id] = {
            "id": point_id,
            "vector": vector,
            "payload": {
                "chunk_text": chunk_text,
                "file_name": file_name,
                "chunk_id": chunk_id,
            },
        }

    def upload_chunks_batch(
        self,
        collection_name: str,
        chunks: List[tuple],
        embedding_func: Callable[[str], List[float]],
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Upload multiple chunks to a collection in batch.

        Args:
            collection_name: Name of the collection
            chunks: List of tuples (chunk_text, file_name, chunk_id)
            embedding_func: Function to generate embeddings
            progress_callback: Optional callback for progress updates

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            CollectionNotFoundError: If collection doesn't exist
            DatabaseOperationError: If operation fails
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        if collection_name not in self._collections:
            raise CollectionNotFoundError(f"Collection '{collection_name}' not found")

        # Process chunks sequentially (simple implementation)
        for chunk_text, file_name, chunk_id in chunks:
            try:
                self.upload_chunk(
                    collection_name, chunk_text, file_name, chunk_id, embedding_func
                )
                if progress_callback:
                    progress_callback(1)
            except Exception as e:
                logger.error(f"Failed to upload chunk {chunk_id} from {file_name}: {e}")
                raise DatabaseOperationError(f"Failed to upload chunk: {e}") from e

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in a collection.

        Args:
            collection_name: Name of the collection
            query_vector: Query vector
            limit: Maximum number of results to return

        Returns:
            List of search results with scores

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            CollectionNotFoundError: If collection doesn't exist
            DatabaseOperationError: If operation fails
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        if collection_name not in self._collections:
            raise CollectionNotFoundError(f"Collection '{collection_name}' not found")

        collection = self._collections[collection_name]
        points = collection["points"]
        config = collection["config"]
        distance_metric = config["distance_metric"]

        if not points:
            return []

        # Simple similarity search using cosine similarity
        results = []
        for point_id, point_data in points.items():
            vector = point_data["vector"]
            score = self._compute_similarity(query_vector, vector, distance_metric)
            results.append(
                {
                    "id": point_id,
                    "score": score,
                    "payload": point_data["payload"],
                }
            )

        # Sort by score (descending) and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _compute_similarity(
        self, vec1: List[float], vec2: List[float], metric: str
    ) -> float:
        """
        Compute similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector
            metric: Distance metric (Cosine, Euclid, Dot)

        Returns:
            Similarity score
        """
        if metric == "Cosine":
            # Cosine similarity
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = sum(a * a for a in vec1) ** 0.5
            magnitude2 = sum(b * b for b in vec2) ** 0.5
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            return dot_product / (magnitude1 * magnitude2)
        elif metric == "Dot":
            # Dot product
            return sum(a * b for a, b in zip(vec1, vec2))
        elif metric == "Euclid":
            # Euclidean distance (inverted for similarity)
            distance = sum((a - b) ** 2 for a, b in zip(vec1, vec2)) ** 0.5
            # Return negative distance as similarity (closer = higher score)
            return -distance
        else:
            raise DatabaseOperationError(f"Unsupported distance metric: {metric}")


# Register the adapter
register_adapter("inmemory", _create_inmemory_adapter)
