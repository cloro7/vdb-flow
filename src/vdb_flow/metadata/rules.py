"""Deterministic extraction from ADR markdown and filename."""

import re
from typing import Any, Dict, Tuple

# Max length for using a non-heading first line as title (avoids using a full paragraph or file).
_MAX_TITLE_LINE_FALLBACK_CHARS = 200


def _skip_optional_yaml_frontmatter(lines: list[str]) -> list[str]:
    """If the file starts with ``---``, skip lines until a closing ``---`` (GitHub-style frontmatter)."""
    if not lines or lines[0].strip() != "---":
        return lines
    for i in range(1, min(len(lines), 300)):
        if lines[i].strip() == "---":
            return lines[i + 1 :]
    return lines


def _title_from_stem(stem: str) -> str:
    """Human-ish title from filename stem when markdown has no usable heading."""
    if not stem.strip():
        return ""
    s = re.sub(r"[-_]+", " ", stem.strip())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_title_from_markdown(text: str, stem: str = "") -> str:
    """
    Prefer the first ATX H1 (``# Title``) after optional YAML frontmatter.

    If there is no H1: use the first non-empty line only when it is short (not a paragraph);
    otherwise fall back to a prettified filename ``stem``, then ``Untitled ADR``.

    A single-line document without an H1 no longer uses the entire body as the title.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = _skip_optional_yaml_frontmatter(text.splitlines())
    for line in lines:
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^#\s+(.+)$", s)
        if m:
            t = m.group(1).strip()
            t = re.sub(r"\s+#+\s*$", "", t).strip()
            return t
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if len(s) <= _MAX_TITLE_LINE_FALLBACK_CHARS:
            return s
        break
    fallback = _title_from_stem(stem)
    return fallback if fallback else "Untitled ADR"


def extract_status_from_markdown(text: str) -> str:
    """Best-effort ## Status section first line."""
    lines = text.splitlines()
    in_status = False
    for line in lines:
        s = line.strip()
        if re.match(r"^##\s+status\s*$", s, re.I):
            in_status = True
            continue
        if in_status:
            if s.startswith("##"):
                break
            if s:
                return s
    return ""


def adr_id_from_stem(stem: str) -> str:
    """
    Prefer patterns like adr-001, ADR-42, or numeric prefix.

    Falls back to full stem.
    """
    m = re.match(r"(?i)^adr-(\d+)", stem)
    if m:
        return m.group(1)
    m = re.match(r"^(\d+)[-_]", stem)
    if m:
        return m.group(1)
    return stem


def build_rules_draft(
    rel_path: str,
    stem: str,
    markdown: str,
    document_kind: str = "adr",
) -> Tuple[Dict[str, Any], str]:
    """
    Build a draft metadata dict and content hash placeholder.

    content_hash must be filled by resolver after normalization.

    Args:
        document_kind: Stored on every point for filters; default ``adr`` for ADR loads.
    """
    title = extract_title_from_markdown(markdown, stem=stem)
    status = extract_status_from_markdown(markdown)
    adr_id = adr_id_from_stem(stem)
    return (
        {
            "metadata_schema_version": "1",
            "document_kind": document_kind,
            "adr_id": adr_id,
            "title": title,
            "status": status,
            "content_hash": "",
            "code_scope": ["general"],
            "tags": [],
            "metadata_source": "generated",
            "metadata_file": None,
        },
        rel_path,
    )
