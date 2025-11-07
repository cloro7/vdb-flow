"""Database adapters for hexagonal architecture."""

from .qdrant import QdrantVectorDatabase

__all__ = ["QdrantVectorDatabase"]

# Import qdrant module to trigger adapter registration
# The registration happens at module import time
from . import qdrant  # noqa: F401, E402
