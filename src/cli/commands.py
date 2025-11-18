"""CLI command handlers."""

import os
import sys
import time
import logging
from typing import Optional

from ..database.port import VectorDatabase, CollectionNotFoundError
from ..database.adapters.qdrant import QdrantNetworkError, QdrantError
from ..services.collection import CollectionService

logger = logging.getLogger(__name__)


class CLICommands:
    """Command handlers for CLI operations."""

    def __init__(self, db_client: VectorDatabase):
        """
        Initialize CLI commands.

        Args:
            db_client: Vector database client
        """
        self.collection_service = CollectionService(db_client)

    def create_collection(
        self,
        collection_name: str,
        distance_metric: str = "Cosine",
        enable_hybrid: bool = True,
        vector_size: Optional[int] = None,
    ) -> None:
        """
        Create a new collection.

        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric to use (Cosine, Euclid, Dot)
            enable_hybrid: Enable hybrid search with sparse vectors
            vector_size: Size of embedding vectors (defaults to config value)

        Raises:
            ValueError: If vector_size is invalid (non-positive)
        """
        try:
            created_collection = self.collection_service.create_collection(
                collection_name,
                distance_metric,
                enable_hybrid=enable_hybrid,
                vector_size=vector_size,
            )
            logger.info(f"Created collection: {created_collection}")
        except (QdrantNetworkError, QdrantError) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)
        except ValueError as e:
            logger.error(str(e))
            raise

    def delete_collection(self, collection_name: str) -> None:
        """Delete an existing collection."""
        try:
            self.collection_service.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except CollectionNotFoundError as e:
            logger.error(f"Collection not found: {e}")
            sys.exit(1)
        except (QdrantNetworkError, QdrantError) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def clear_collection(self, collection_name: str) -> None:
        """Clear all points from a collection."""
        try:
            self.collection_service.clear_collection(collection_name)
            logger.info(f"Cleared collection: {collection_name}")
        except (QdrantNetworkError, QdrantError) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def list_collections(self) -> None:
        """List all collections."""
        try:
            collections = self.collection_service.list_collections()
            logger.info(f"Listed collections: {collections}")
        except (QdrantNetworkError, QdrantError) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def get_collection_info(self, collection_name: str) -> None:
        """Get information about a collection."""
        try:
            collection_info = self.collection_service.get_collection_info(
                collection_name
            )
            logger.info(f"Collection info: {collection_info}")
        except (QdrantNetworkError, QdrantError) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def load_collection(self, collection_name: str, path: str) -> None:
        """
        Load ADRs from a directory into a collection.

        Args:
            collection_name: Name of the collection
            path: Path to ADR directory

        Raises:
            SystemExit: If path doesn't exist or collection doesn't exist
        """
        adr_path = os.path.expanduser(path)
        if not os.path.exists(adr_path):
            logger.error(f"Path not found: {adr_path}")
            sys.exit(1)

        start_time = time.time()
        logger.info(
            f"Loading ADRs from {adr_path} into collection '{collection_name}' ..."
        )

        try:
            self.collection_service.load_collection(collection_name, adr_path)
        except (QdrantNetworkError, QdrantError) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)
        except RuntimeError as e:
            # Embedding service connection errors
            logger.error(f"Embedding service error: {e}")
            logger.error(
                "Please check that Ollama is running and accessible at the configured URL."
            )
            sys.exit(1)

        elapsed = time.time() - start_time
        minutes, seconds = divmod(elapsed, 60)
        logger.info(f"Done! Total runtime: {int(minutes)}m {seconds:.1f}s")
