"""Embedding module (hexagonal architecture — port + adapter registry)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, List

from .port import EmbeddingError, EmbeddingProvider

if TYPE_CHECKING:
    from ..config import Config

__all__ = [
    "EmbeddingProvider",
    "EmbeddingError",
    "create_embedding_provider",
    "register_embedding_adapter",
    "get_available_embedding_adapters",
]

logger = logging.getLogger(__name__)

_EMBEDDING_ADAPTERS: Dict[str, Callable[..., EmbeddingProvider]] = {}


def register_embedding_adapter(
    name: str, factory: Callable[..., EmbeddingProvider]
) -> None:
    """Register an embedding adapter factory (type name -> provider constructor)."""
    _EMBEDDING_ADAPTERS[name.lower()] = factory


def get_available_embedding_adapters() -> List[str]:
    """Return sorted list of registered embedding adapter names."""
    global _EMBEDDING_ENTRY_POINTS_LOADED
    if not _EMBEDDING_ENTRY_POINTS_LOADED:
        _load_embedding_entry_points()
        _EMBEDDING_ENTRY_POINTS_LOADED = True
    return sorted(_EMBEDDING_ADAPTERS.keys())


def _get_entry_points():
    try:
        from importlib.metadata import entry_points
    except ImportError:
        try:
            from importlib_metadata import entry_points
        except ImportError:
            return []
    try:
        return entry_points(group="vdb_flow.embedding_adapters")
    except TypeError:
        try:
            all_eps = entry_points()
            return all_eps.get("vdb_flow.embedding_adapters", [])
        except Exception:
            return []


def _load_embedding_entry_points() -> None:
    for ep in _get_entry_points():
        try:
            register_fn = ep.load()
            register_fn()
            logger.debug("Loaded embedding adapter entry point '%s'", ep.name)
        except Exception as e:
            logger.warning("Failed to load embedding entry point '%s': %s", ep.name, e)


_EMBEDDING_ENTRY_POINTS_LOADED = False


def create_embedding_provider(config: Config) -> EmbeddingProvider:
    """
    Instantiate the configured EmbeddingProvider (port) from the adapter registry.

    Args:
        config: Application configuration (embeddings.type selects the adapter).

    Returns:
        EmbeddingProvider implementation
    """
    global _EMBEDDING_ENTRY_POINTS_LOADED
    if not _EMBEDDING_ENTRY_POINTS_LOADED:
        _load_embedding_entry_points()
        _EMBEDDING_ENTRY_POINTS_LOADED = True

    adapter_type = config.embedding_adapter_type.lower()
    try:
        factory = _EMBEDDING_ADAPTERS[adapter_type]
    except KeyError:
        available = ", ".join(get_available_embedding_adapters()) or "none"
        raise ValueError(
            f"Unsupported embeddings.type: {adapter_type}. "
            f"Available adapters: {available}"
        ) from None

    return factory(config)


# Register built-in adapters (after registry API is defined)
from . import adapters  # noqa: E402
