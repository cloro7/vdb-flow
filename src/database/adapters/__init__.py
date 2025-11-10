"""Database adapters for hexagonal architecture."""

from .qdrant import QdrantVectorDatabase
from .inmemory import InMemoryVectorDatabase

__all__ = ["QdrantVectorDatabase", "InMemoryVectorDatabase"]

# Import adapter modules to trigger adapter registration
# The registration happens at module import time
from . import qdrant  # noqa: F401, E402
from . import inmemory  # noqa: F401, E402
