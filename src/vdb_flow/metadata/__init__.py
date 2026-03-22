"""ADR metadata resolution (optional sidecar JSON, rules, LLM enrichment)."""

from .resolver import (
    MetadataResolver,
    content_hash_from_text,
    metadata_for_payload,
    resolve_adr_metadata,
)

__all__ = [
    "MetadataResolver",
    "content_hash_from_text",
    "metadata_for_payload",
    "resolve_adr_metadata",
]
