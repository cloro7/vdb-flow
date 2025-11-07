"""Database module following hexagonal architecture."""

from typing import Optional, Callable, Dict, List
from .port import VectorDatabase

__all__ = [
    "VectorDatabase",
    "VectorDatabaseError",
    "CollectionNotFoundError",
    "create_vector_database",
    "register_adapter",
    "get_available_adapters",
]

# Adapter registry: maps database type names to factory functions
_ADAPTERS: Dict[str, Callable[..., VectorDatabase]] = {}


def register_adapter(name: str, factory: Callable[..., VectorDatabase]) -> None:
    """
    Register a database adapter factory.

    This allows adapters to register themselves, making the system pluggable.
    Third-party adapters can call this function to add support for new database types.

    Args:
        name: Database type name (e.g., 'qdrant', 'pinecone', 'weaviate')
        factory: Factory function that creates a VectorDatabase instance.
                Should accept keyword arguments and return a VectorDatabase.

    Example:
        >>> register_adapter("qdrant", lambda qdrant_url=None: QdrantVectorDatabase(qdrant_url=qdrant_url))
    """
    _ADAPTERS[name.lower()] = factory


def get_available_adapters() -> List[str]:
    """
    Get list of available database adapter names.

    This function ensures entry-point adapters are loaded before returning
    the list, so third-party adapters are included.

    Returns:
        List of registered adapter names
    """
    global _ENTRY_POINTS_LOADED
    if not _ENTRY_POINTS_LOADED:
        _load_entry_point_adapters()
        _ENTRY_POINTS_LOADED = True
    return sorted(_ADAPTERS.keys())


def _get_entry_points():
    """
    Get entry points for vdb_manager.adapters, handling Python version differences.

    Returns:
        Iterable of entry points, or empty list if not available
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:
        # Python < 3.8 fallback
        try:
            from importlib_metadata import entry_points
        except ImportError:
            return []  # No entry points support available

    try:
        # Python 3.10+ supports group= keyword argument
        return entry_points(group="vdb_manager.adapters")
    except TypeError:
        # Fall back to Python 3.8/3.9 API
        try:
            all_entry_points = entry_points()
            return all_entry_points.get("vdb_manager.adapters", [])
        except Exception:
            return []


def _load_single_entry_point(entry_point, logger):
    """
    Load and register a single entry point adapter.

    Args:
        entry_point: Entry point object to load
        logger: Logger instance for error reporting
    """
    try:
        register_func = entry_point.load()
        register_func()
        logger.debug(f"Loaded adapter entry point '{entry_point.name}'")
    except Exception as e:
        logger.warning(f"Failed to load adapter entry point '{entry_point.name}': {e}")


def _load_entry_point_adapters():
    """
    Load adapters registered via setuptools entry points.

    This allows third-party packages to register adapters without modifying
    core code. Entry points should be defined in pyproject.toml under:
    [project.entry-points."vdb_manager.adapters"]

    The entry point should be a callable that performs the registration,
    typically by calling register_adapter().
    """
    import logging

    logger = logging.getLogger(__name__)

    entry_points_iter = _get_entry_points()
    if not entry_points_iter:
        return

    for entry_point in entry_points_iter:
        _load_single_entry_point(entry_point, logger)


# Track whether entry points have been loaded
_ENTRY_POINTS_LOADED = False


def create_vector_database(
    db_type: str = "qdrant", qdrant_url: Optional[str] = None, **kwargs
) -> VectorDatabase:
    """
    Create a VectorDatabase instance using the adapter registry.

    This function serves as the composition root for dependency injection.
    It uses the adapter registry to find and instantiate the appropriate
    implementation based on the provided database type.

    Args:
        db_type: Database type (e.g., 'qdrant', 'pinecone', 'weaviate').
                Defaults to 'qdrant'.
        qdrant_url: Optional Qdrant URL. Only used when db_type is 'qdrant'.
                   If None, QdrantVectorDatabase will use config default.
        **kwargs: Additional keyword arguments passed to the adapter factory.

    Returns:
        VectorDatabase instance (port interface)

    Raises:
        ValueError: If the database type is not supported.

    Example:
        >>> db = create_vector_database("qdrant", qdrant_url="http://localhost:6333")
        >>> db = create_vector_database("pinecone", api_key="...", environment="...")
    """
    # Load entry point adapters on first call (only once)
    global _ENTRY_POINTS_LOADED
    if not _ENTRY_POINTS_LOADED:
        _load_entry_point_adapters()
        _ENTRY_POINTS_LOADED = True

    db_type_lower = db_type.lower()

    try:
        factory = _ADAPTERS[db_type_lower]
    except KeyError:
        available = ", ".join(get_available_adapters()) or "none"
        raise ValueError(
            f"Unsupported database type: {db_type}. " f"Available adapters: {available}"
        )

    # For backward compatibility, pass qdrant_url as a kwarg if provided
    if qdrant_url is not None:
        kwargs["qdrant_url"] = qdrant_url

    return factory(**kwargs)


# Import built-in adapters to trigger their registration
# This ensures Qdrant adapter is always available
# The import must happen after register_adapter is defined
from .adapters import qdrant  # noqa: E402
