"""LLM provider protocol for ADR metadata enrichment."""

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class LlmProvider(Protocol):
    """Optional enrichment: e.g. code_scope and tags from markdown."""

    def is_enabled(self) -> bool:
        """Whether this provider will perform calls (False for no-op)."""
        ...

    def enrich_adr_metadata(
        self, markdown: str, draft: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Return partial metadata fields to merge into draft (e.g. code_scope, tags).

        Must not replace adr_id/title from draft unless explicitly intended.
        """
        ...
