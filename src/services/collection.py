"""Collection service for loading and managing ADR collections."""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

from tqdm import tqdm

from ..constants import DEFAULT_BATCH_SIZE
from ..database.port import VectorDatabase
from ..database.adapters.qdrant import QdrantCollectionNotFoundError
from ..validation import (
    validate_collection_name,
    validate_distance_metric,
    validate_path,
)
from .text_processing import clean_text, chunk_text
from .embedding import get_embedding

logger = logging.getLogger(__name__)

# Use constant for batch size
BATCH_SIZE = DEFAULT_BATCH_SIZE


class CollectionService:
    """Service for managing ADR collections."""

    def __init__(self, db_client: VectorDatabase):
        """
        Initialize collection service.

        Args:
            db_client: Vector database client implementing VectorDatabase port
        """
        self.db_client = db_client

    @staticmethod
    def _read_file_with_fallback(file_path: str, rel_path: str) -> str:
        """
        Read file with encoding fallback handling.

        Args:
            file_path: Absolute path to the file
            rel_path: Relative path for logging purposes

        Returns:
            File contents as string

        Raises:
            UnicodeDecodeError: If file cannot be read even with fallback
            IOError: If file cannot be opened
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with error handling for files with encoding issues
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                logger.warning(
                    f"File {rel_path} had encoding issues, "
                    f"replaced invalid characters with replacement markers"
                )
                return text
            except Exception as e:
                logger.error(f"Failed to read file {rel_path}: {e}")
                raise

    def create_collection(
        self,
        collection_name: str,
        distance_metric: str = "Cosine",
        enable_hybrid: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new collection.

        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric to use (Cosine, Euclid, Dot)
            enable_hybrid: Enable hybrid search with sparse vectors

        Returns:
            Collection information

        Raises:
            ValueError: If collection name or distance metric is invalid
        """
        validate_collection_name(collection_name)
        validate_distance_metric(distance_metric)
        return self.db_client.create_collection(
            collection_name, distance_metric, enable_hybrid=enable_hybrid
        )

    def delete_collection(self, collection_name: str) -> None:
        """
        Delete an existing collection.

        Args:
            collection_name: Name of the collection to delete

        Raises:
            ValueError: If collection name is invalid
        """
        validate_collection_name(collection_name)
        self.db_client.delete_collection(collection_name)

    def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Clear all points from a collection without deleting it.

        Args:
            collection_name: Name of the collection

        Returns:
            Operation result

        Raises:
            ValueError: If collection name is invalid
        """
        validate_collection_name(collection_name)
        return self.db_client.clear_collection(collection_name)

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections.

        Returns:
            List of collection information
        """
        return self.db_client.list_collections()

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Collection information

        Raises:
            ValueError: If collection name is invalid
        """
        validate_collection_name(collection_name)
        return self.db_client.get_collection_info(collection_name)

    def _validate_collection_exists(self, collection_name: str) -> None:
        """
        Validate that collection exists before loading.

        Args:
            collection_name: Name of the collection to validate

        Raises:
            ValueError: If collection does not exist
        """
        try:
            collection_info = self.db_client.get_collection_info(collection_name)
            if not collection_info or not collection_info.get("result"):
                raise ValueError(
                    f"Collection '{collection_name}' does not exist. "
                    f"Please create it first using the 'create' command."
                )
        except QdrantCollectionNotFoundError:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Please create it first using the 'create' command."
            )

    def _discover_md_files(self, validated_path: Path) -> List[Tuple[str, str, int]]:
        """
        Discover all .md files and count their chunks.

        Args:
            validated_path: Validated path to search

        Returns:
            List of tuples (file_path, rel_path, num_chunks)
        """
        md_files = []
        path_str = str(validated_path)
        for root, _, files in os.walk(path_str):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, path_str)
                    # Count chunks for this file with encoding error handling
                    try:
                        text = self._read_file_with_fallback(file_path, rel_path)
                        text = clean_text(text)
                    except (UnicodeDecodeError, IOError) as e:
                        logger.error(f"Failed to read file {rel_path}: {e}")
                        continue
                    chunks = chunk_text(text)
                    md_files.append((file_path, rel_path, len(chunks)))
        return md_files

    def _collect_all_chunks(
        self, md_files: List[Tuple[str, str, int]]
    ) -> List[Tuple[str, str, int]]:
        """
        Collect all chunks from discovered files.

        Args:
            md_files: List of tuples (file_path, rel_path, num_chunks)

        Returns:
            List of tuples (chunk_text, file_name, chunk_id)
        """
        all_chunks: List[Tuple[str, str, int]] = []
        for file_path, rel_path, num_chunks in md_files:
            try:
                text = self._read_file_with_fallback(file_path, rel_path)
                text = clean_text(text)
            except (UnicodeDecodeError, IOError) as e:
                logger.error(f"Failed to read file {rel_path}: {e}")
                continue
            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append((chunk, rel_path, i + 1))
        return all_chunks

    def _process_batch_with_fallback(
        self,
        collection_name: str,
        batch: List[Tuple[str, str, int]],
        pbar: Any,
    ) -> int:
        """
        Process a batch of chunks with fallback to individual uploads.

        Args:
            collection_name: Name of the collection
            batch: List of tuples (chunk_text, file_name, chunk_id)
            pbar: Progress bar to update

        Returns:
            Number of successfully processed chunks
        """
        processed = 0

        # Progress callback to update progress bar incrementally
        def progress_callback(count: int) -> None:
            pbar.update(count)
            pbar.refresh()  # Force immediate refresh

        try:
            self.db_client.upload_chunks_batch(
                collection_name,
                batch,
                get_embedding,
                progress_callback=progress_callback,
            )
            processed = len(batch)
        except Exception as e:
            logger.warning(
                f"Batch upload failed, falling back to individual uploads: {e}"
            )
            # Fallback to individual uploads for this batch
            for chunk_content, file_name, chunk_id in batch:
                try:
                    self.db_client.upload_chunk(
                        collection_name,
                        chunk_content,
                        file_name,
                        chunk_id,
                        get_embedding,
                    )
                    processed += 1
                    pbar.update(1)
                    pbar.refresh()  # Force immediate refresh
                except Exception as e2:
                    logger.error(f"Failed to upload chunk {file_name}-{chunk_id}: {e2}")
        return processed

    def load_collection(self, collection_name: str, path: str) -> None:
        """
        Recursively read all .md ADRs from path, chunk them, and upload.

        Args:
            collection_name: Name of the collection
            path: Path to ADR directory (can include subfolders)

        Raises:
            ValueError: If collection does not exist or validation fails
            FileNotFoundError: If path does not exist
            UnicodeDecodeError: If file encoding cannot be handled
        """
        # Validate inputs
        validate_collection_name(collection_name)
        validated_path = validate_path(path, must_exist=True)

        # Validate that collection exists
        self._validate_collection_exists(collection_name)

        # Discover all .md files and count chunks
        md_files = self._discover_md_files(validated_path)
        if not md_files:
            logger.warning(f"No .md files found in {path}")
            return

        total_chunks = sum(num_chunks for _, _, num_chunks in md_files)

        # Collect all chunks with metadata for batch processing
        all_chunks = self._collect_all_chunks(md_files)

        # Process chunks in batches with parallel embedding generation
        with tqdm(
            total=len(all_chunks),
            desc="Processing chunks",
            unit="chunk",
            leave=True,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} chunks [{elapsed}<{remaining}, {rate_fmt}]",
        ) as pbar:
            # Process in batches
            for batch_start in range(0, len(all_chunks), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(all_chunks))
                batch = all_chunks[batch_start:batch_end]
                self._process_batch_with_fallback(collection_name, batch, pbar)

        logger.info(
            f"Successfully loaded {len(md_files)} files ({total_chunks} chunks) "
            f"into collection '{collection_name}'"
        )
