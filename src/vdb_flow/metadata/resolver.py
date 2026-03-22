"""Resolve ADR metadata: sidecar JSON > rules (+ optional LLM)."""

from __future__ import annotations

import hashlib
import json
import logging
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from .code_scope import apply_code_scope_normalization
from .repo_type import apply_repo_type_normalization
from .rules import build_rules_draft

if TYPE_CHECKING:
    from ..config import Config
    from ..llm.base import LlmProvider

logger = logging.getLogger(__name__)

_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def _load_schema_v1() -> Dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    pkg = "vdb_flow.metadata.schema"
    with (
        resources.files(pkg)
        .joinpath("adr_metadata_v1.json")
        .open("r", encoding="utf-8") as f
    ):
        _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def _validate_metadata(obj: Dict[str, Any]) -> None:
    try:
        import jsonschema

        jsonschema.validate(instance=obj, schema=_load_schema_v1())
    except ImportError as e:
        raise RuntimeError(
            "jsonschema is required for ADR metadata validation. "
            "Install with: pip install jsonschema"
        ) from e


def content_hash_from_text(markdown: str) -> str:
    """SHA-256 hex of UTF-8 encoded markdown (must match stored ``content_hash``)."""
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def _sidecar_path(md_path: Path, suffix: str) -> Path:
    return md_path.parent / f"{md_path.stem}{suffix}"


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    import json

    t = _strip_json_fence(raw)
    return json.loads(t)


class MetadataResolver:
    """
    Resolve metadata for one markdown file (default kind: ADR).

    Precedence: valid sidecar JSON > merged (rules + optional LLM enrich).
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        metadata_suffix: str = ".metadata.json",
        llm_provider: Optional["LlmProvider"] = None,
        use_llm_when_no_file: bool = True,
        document_kind: str = "adr",
    ):
        """Configure resolver: sidecar suffix, optional LLM, document kind."""
        self.enabled = enabled
        self.metadata_suffix = metadata_suffix
        self.llm_provider = llm_provider
        self.use_llm_when_no_file = use_llm_when_no_file
        self.document_kind = document_kind

    def resolve(
        self,
        md_absolute: str,
        rel_path: str,
        markdown: str,
    ) -> Optional[Dict[str, Any]]:
        """Return payload metadata for Qdrant, or None if metadata is disabled."""
        if not self.enabled:
            return None

        md_path = Path(md_absolute)
        stem = md_path.stem
        draft, _ = build_rules_draft(
            rel_path, stem, markdown, document_kind=self.document_kind
        )
        ch = content_hash_from_text(markdown)
        draft["content_hash"] = ch

        sidecar = _sidecar_path(md_path, self.metadata_suffix)
        if sidecar.is_file():
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    from_file = json.load(f)
                if not isinstance(from_file, dict):
                    raise ValueError("metadata file must be a JSON object")
                merged = {**draft, **from_file}
                merged["content_hash"] = ch
                merged["metadata_source"] = "file"
                merged["metadata_file"] = (
                    str(Path(rel_path).parent / sidecar.name)
                    if rel_path
                    else sidecar.name
                )
                apply_code_scope_normalization(merged)
                apply_repo_type_normalization(merged)
                _validate_metadata(merged)
                return merged
            except Exception as e:
                logger.warning(
                    "Invalid or unreadable metadata file %s: %s — falling back to rules",
                    sidecar,
                    e,
                )

        # Generated path: rules + optional LLM
        draft["metadata_source"] = "generated"
        draft["metadata_file"] = None

        if (
            self.use_llm_when_no_file
            and self.llm_provider is not None
            and self.llm_provider.is_enabled()
        ):
            try:
                enriched = self.llm_provider.enrich_adr_metadata(
                    markdown=markdown, draft=draft
                )
                merged = {**draft, **enriched}
                merged["content_hash"] = ch
                merged["metadata_source"] = "merged"
                merged["metadata_file"] = None
                apply_code_scope_normalization(merged)
                apply_repo_type_normalization(merged)
                _validate_metadata(merged)
                return merged
            except Exception as e:
                logger.warning(
                    "LLM metadata enrichment failed: %s — using rules only", e
                )

        apply_code_scope_normalization(draft)
        apply_repo_type_normalization(draft)
        _validate_metadata(draft)
        return draft


def resolve_adr_metadata(
    config: "Config",
    md_absolute: str,
    rel_path: str,
    markdown: str,
    llm_provider: Optional["LlmProvider"],
    *,
    metadata_enabled: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve ADR metadata using Config (optional ``metadata_enabled`` overrides config)."""
    enabled = config.metadata_enabled if metadata_enabled is None else metadata_enabled
    resolver = MetadataResolver(
        enabled=enabled,
        metadata_suffix=config.metadata_suffix,
        llm_provider=llm_provider,
        use_llm_when_no_file=config.use_llm_when_no_sidecar,
        document_kind=config.metadata_document_kind,
    )
    return resolver.resolve(md_absolute, rel_path, markdown)


def metadata_for_payload(meta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strip or normalize for storage in vector payload (flattened)."""
    if meta is None:
        return None
    # Store only JSON-serializable flat fields Qdrant accepts
    out: Dict[str, Any] = {}
    for k, v in meta.items():
        if v is None and k == "metadata_file":
            out[k] = None
        elif v is not None:
            out[k] = v
    return out
