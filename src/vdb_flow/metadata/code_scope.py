"""Allowed ``code_scope`` values and normalization (closed vocabulary + ``general`` fallback)."""

from __future__ import annotations

from typing import Any, Dict, List

# Keep in sync with ``adr_metadata_v1.json`` ``code_scope.items.enum``.
ALLOWED_CODE_SCOPES: tuple[str, ...] = (
    "cpp",
    "csharp",
    "rust",
    "yaml",
    "json",
    "dockerfile",
    "general",
)


def normalize_code_scope(value: Any) -> List[str]:
    r"""
    Return a non-empty list of allowed scope strings.

    Unknown or invalid entries are dropped. If nothing remains, returns ``[\"general\"]``.
    Order is preserved; duplicates are removed (first occurrence wins).
    """
    allowed = frozenset(ALLOWED_CODE_SCOPES)
    if not isinstance(value, list):
        return ["general"]
    out: List[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        s = item.strip().lower()
        if s not in allowed or s in seen:
            continue
        seen.add(s)
        out.append(s)
    if not out:
        return ["general"]
    return out


def apply_code_scope_normalization(meta: Dict[str, Any]) -> None:
    """Mutate ``meta`` in place: set ``code_scope`` to a validated non-empty list."""
    meta["code_scope"] = normalize_code_scope(meta.get("code_scope"))
