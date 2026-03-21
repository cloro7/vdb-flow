"""Composition root for dependency injection.

This module provides a centralized place to wire together all dependencies,
following the dependency injection pattern. Services and CLI components
receive their dependencies rather than accessing global config directly.
"""

import logging
from typing import Callable, List, Optional

from .config import Config, get_config
from .database import create_vector_database, VectorDatabase
from .embeddings import EmbeddingProvider, create_embedding_provider
from .services.collection import CollectionService

logger = logging.getLogger(__name__)


class ApplicationContainer:
    """Container for application dependencies."""

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the application container.

        Args:
            config: Optional Config instance. If None, will load from default location.
        """
        self._config = config or get_config()
        self._db_client: Optional[VectorDatabase] = None
        self._embedding_provider: Optional[EmbeddingProvider] = None
        self._collection_service: Optional[CollectionService] = None

    @property
    def config(self) -> Config:
        """Get the configuration instance."""
        return self._config

    @property
    def db_client(self) -> VectorDatabase:
        """
        Get or create the database client.

        Returns:
            VectorDatabase instance
        """
        if self._db_client is None:
            self._db_client = create_vector_database(
                db_type=self._config.database_type,
                qdrant_url=(
                    self._config.qdrant_url
                    if self._config.database_type.lower() == "qdrant"
                    else None
                ),
            )
        return self._db_client

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        """Embedding port (adapter chosen via config embeddings.type)."""
        if self._embedding_provider is None:
            self._embedding_provider = create_embedding_provider(self._config)
        return self._embedding_provider

    @property
    def collection_service(self) -> CollectionService:
        """
        Get or create the collection service.

        Returns:
            CollectionService instance
        """
        if self._collection_service is None:
            self._collection_service = CollectionService(
                self.db_client,
                embedding_func=self.get_embedding_func(),
                config=self._config,
            )
        return self._collection_service

    def get_embedding_func(self) -> Callable[[str], List[float]]:
        """
        Callable that delegates to the configured EmbeddingProvider.embed.

        Returns:
            Callable that takes text and returns embedding vector
        """
        return self.embedding_provider.embed


# Global container instance (lazy-initialized)
_container: Optional[ApplicationContainer] = None


def get_container(config: Optional[Config] = None) -> ApplicationContainer:
    """
    Get or create the global application container.

    Args:
        config: Optional Config instance. Only used on first call.

    Returns:
        ApplicationContainer instance
    """
    global _container
    if _container is None:
        _container = ApplicationContainer(config)
    return _container


def reset_container():
    """Reset the global container (useful for testing)."""
    global _container
    _container = None
