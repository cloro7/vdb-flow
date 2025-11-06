"""Database module following hexagonal architecture."""

from typing import Optional
from .port import VectorDatabase
from .adapters import QdrantVectorDatabase

__all__ = [
    "VectorDatabase",
    "QdrantVectorDatabase",
    "create_vector_database",
]


def create_vector_database(
    db_type: str = "qdrant", qdrant_url: Optional[str] = None
) -> VectorDatabase:
    """
    Create a VectorDatabase instance.

    This function serves as the composition root for dependency injection.
    It returns the appropriate implementation based on the provided database type.

    Args:
        db_type: Database type (e.g., 'qdrant', 'pinecone', 'weaviate').
                Defaults to 'qdrant'.
        qdrant_url: Optional Qdrant URL. Only used when db_type is 'qdrant'.
                   If None, QdrantVectorDatabase will use config default.

    Returns:
        VectorDatabase instance (port interface)

    Raises:
        ValueError: If the database type is not supported.
    """
    db_type_lower = db_type.lower()

    if db_type_lower == "qdrant":
        return QdrantVectorDatabase(qdrant_url=qdrant_url)
    # Future implementations can be added here:
    # elif db_type_lower == "pinecone":
    #     from .adapters.pinecone import PineconeVectorDatabase
    #     return PineconeVectorDatabase(...)
    # elif db_type_lower == "weaviate":
    #     from .adapters.weaviate import WeaviateVectorDatabase
    #     return WeaviateVectorDatabase(...)
    else:
        raise ValueError(
            f"Unsupported database type: {db_type}. " f"Supported types: 'qdrant'"
        )
