"""Database port for hexagonal architecture."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable, Tuple, Optional

from ..constants import DEFAULT_VECTOR_SIZE


class VectorDatabase(ABC):
    """Abstract interface for vector database operations (port)."""

    @abstractmethod
    def create_collection(
        self,
        collection_name: str,
        distance_metric: str = "Cosine",
        vector_size: int = DEFAULT_VECTOR_SIZE,
        enable_hybrid: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new vector collection.

        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric (Cosine, Euclid, Dot)
            vector_size: Size of the vectors
            enable_hybrid: Enable hybrid search with sparse vectors

        Returns:
            Collection information
        """
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        """
        Delete a collection.

        Args:
            collection_name: Name of the collection to delete
        """
        pass

    @abstractmethod
    def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Clear all points from a collection without deleting it.

        Args:
            collection_name: Name of the collection

        Returns:
            Operation result
        """
        pass

    @abstractmethod
    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections.

        Returns:
            List of collection information
        """
        pass

    @abstractmethod
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Collection information
        """
        pass

    @abstractmethod
    def upload_chunk(
        self,
        collection: str,
        chunk_text: str,
        file_name: str,
        chunk_id: int,
        embedding_func: Callable[[str], List[float]],
    ) -> None:
        """
        Upload a text chunk with its embedding to the database.

        Args:
            collection: Collection name
            chunk_text: Text content of the chunk
            file_name: Source file name
            chunk_id: Chunk identifier
            embedding_func: Function to generate embeddings
        """
        pass

    def upload_chunks_batch(
        self,
        collection: str,
        chunks: List[Tuple[str, str, int]],
        embedding_func: Callable[[str], List[float]],
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Upload multiple chunks in a single batch operation.

        This is an optional method for performance optimization. If not implemented,
        the adapter should fall back to individual upload_chunk calls.

        Args:
            collection: Collection name
            chunks: List of tuples (chunk_text, file_name, chunk_id)
            embedding_func: Function to generate embeddings
            progress_callback: Optional callback to report progress (called with number of chunks processed)
        """
        # Default implementation: fall back to individual uploads
        for chunk_text, file_name, chunk_id in chunks:
            self.upload_chunk(
                collection, chunk_text, file_name, chunk_id, embedding_func
            )
            if progress_callback:
                progress_callback(1)

    @abstractmethod
    def search(
        self, collection_name: str, vector: List[float], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in a collection.

        Args:
            collection_name: Name of the collection to search
            vector: Query vector
            limit: Maximum number of results

        Returns:
            List of search results with score and payload
        """
        pass
