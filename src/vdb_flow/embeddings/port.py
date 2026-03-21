"""Embedding port (hexagonal architecture — application boundary)."""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingError(RuntimeError):
    """Raised when embedding generation fails after retries or configuration is invalid."""

    pass


class EmbeddingProvider(ABC):
    """
    Port for text embedding generation.

    Implementations live in adapters (e.g. HTTP backends); the domain layer
    depends only on this interface.
    """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Embed a single text chunk.

        Args:
            text: Input text (implementations may truncate per config)

        Returns:
            Embedding vector

        Raises:
            EmbeddingError: On persistent failure to obtain an embedding
        """
        pass
