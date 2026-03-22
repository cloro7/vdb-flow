"""No-op LLM provider (default)."""

from typing import Any, Dict


class NoOpLlmProvider:
    """Disabled provider: never enriches."""

    def is_enabled(self) -> bool:
        """Return False (no enrichment)."""
        return False

    def enrich_adr_metadata(
        self, markdown: str, draft: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return an empty dict (no-op)."""
        return {}
