"""CLI command handlers."""

import os
import sys
import time
import logging
from typing import Optional, Dict, Any, List

from ..database.port import (
    CollectionNotFoundError,
    DatabaseConnectionError,
    DatabaseTimeoutError,
    DatabaseOperationError,
    InvalidCollectionNameError,
    InvalidVectorSizeError,
)
from ..services.collection import CollectionService

logger = logging.getLogger(__name__)


def _ensure_logging_configured(default_level: int = logging.INFO) -> None:
    """
    Configure root logger if nothing has set it up yet.

    This covers programmatic entry points (e.g., vdb-list) that call CLICommands
    directly without going through the main CLI setup.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    logging.basicConfig(
        level=default_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class CLICommands:
    """Command handlers for CLI operations."""

    def __init__(self, collection_service: CollectionService):
        """
        Initialize CLI commands.

        Args:
            collection_service: Collection service instance
        """
        _ensure_logging_configured()
        self.collection_service = collection_service

    def create_collection(
        self,
        collection_name: str,
        distance_metric: str = "Cosine",
        enable_hybrid: bool = True,
        vector_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a new collection.

        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric to use (Cosine, Euclid, Dot)
            enable_hybrid: Enable hybrid search with sparse vectors
            vector_size: Size of embedding vectors (defaults to config value)

        Returns:
            Collection information dictionary

        Exits with code 1 on validation or database errors.
        """
        logger.info(f"Creating collection '{collection_name}'...")
        try:
            created_collection = self.collection_service.create_collection(
                collection_name,
                distance_metric,
                enable_hybrid=enable_hybrid,
                vector_size=vector_size,
            )
            logger.info(f"Successfully created collection '{collection_name}'")
            return created_collection
        except InvalidVectorSizeError as e:
            logger.error(f"Invalid vector size: {e}")
            sys.exit(1)
        except InvalidCollectionNameError as e:
            logger.error(f"Invalid collection name: {e}")
            sys.exit(1)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Delete an existing collection.

        Returns:
            Success status dictionary
        """
        logger.info(f"Deleting collection '{collection_name}'...")
        try:
            self.collection_service.delete_collection(collection_name)
            logger.info(f"Successfully deleted collection '{collection_name}'")
            return {"status": "ok", "collection": collection_name}
        except CollectionNotFoundError as e:
            logger.error(f"Collection not found: {e}")
            sys.exit(1)
        except InvalidCollectionNameError as e:
            logger.error(f"Invalid collection name: {e}")
            sys.exit(1)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Clear all points from a collection.

        Returns:
            Operation result dictionary
        """
        logger.info(f"Clearing collection '{collection_name}'...")
        try:
            result = self.collection_service.clear_collection(collection_name)
            logger.info(f"Successfully cleared collection '{collection_name}'")
            return result
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections.

        Returns:
            List of collection information dictionaries
        """
        try:
            collections = self.collection_service.list_collections()
            logger.info(f"Listing collections: {collections}")
            return collections
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.

        Returns:
            Collection information dictionary
        """
        logger.info(f"Getting information for collection '{collection_name}'...")
        try:
            collection_info = self.collection_service.get_collection_info(
                collection_name
            )
            logger.info(
                f"Successfully retrieved information for collection '{collection_name}'"
            )
            return collection_info
        except (
            CollectionNotFoundError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
            logger.error(f"Database error: {e}")
            sys.exit(1)

    def load_collection(self, collection_name: str, path: str) -> Dict[str, Any]:
        """
        Load ADRs from a directory into a collection.

        Args:
            collection_name: Name of the collection
            path: Path to ADR directory

        Returns:
            Success status dictionary with runtime information

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
        except CollectionNotFoundError as e:
            logger.error(f"Collection not found: {e}")
            sys.exit(1)
        except InvalidCollectionNameError as e:
            logger.error(f"Invalid collection name: {e}")
            sys.exit(1)
        except (
            DatabaseConnectionError,
            DatabaseTimeoutError,
            DatabaseOperationError,
        ) as e:
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

        return {
            "status": "ok",
            "collection": collection_name,
            "path": adr_path,
            "runtime_seconds": elapsed,
            "runtime_formatted": f"{int(minutes)}m {seconds:.1f}s",
        }
