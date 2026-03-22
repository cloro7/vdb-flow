r"""Allowed ``repo_type`` values and normalization (default ``[\"all\"]`` for general ADRs)."""

from __future__ import annotations

from typing import Any, Dict, List

# Keep in sync with ``adr_metadata_v1.json`` ``repo_type.items.enum``.
ALLOWED_REPO_TYPES: tuple[str, ...] = (
    "all",
    "unit",
    "tool",
    "library",
)


def normalize_repo_type(value: Any) -> List[str]:
    r"""
    Return a non-empty list of allowed repo-type strings.

    Missing, invalid, or empty input becomes ``[\"all\"]`` (ADR applies to any repo).
    If ``all`` appears together with other tokens, result is ``[\"all\"]`` only.
    Order is preserved; duplicates are removed (first occurrence wins).
    """
    allowed = frozenset(ALLOWED_REPO_TYPES)
    if not isinstance(value, list):
        return ["all"]
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
        return ["all"]
    if "all" in out:
        return ["all"]
    return out


def apply_repo_type_normalization(meta: Dict[str, Any]) -> None:
    """Mutate ``meta`` in place: set ``repo_type`` to a validated non-empty list."""
    meta["repo_type"] = normalize_repo_type(meta.get("repo_type"))
