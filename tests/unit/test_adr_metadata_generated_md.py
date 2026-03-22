"""
ADR metadata resolution tests using a generated Markdown file.

LLM enrichment is covered with a **stub** implementing ``LlmProvider`` — no Claude CLI
or cloud calls. CI stays deterministic and offline.

Optional: set ``VDB_FLOW_TEST_SUBPROCESS_LLM=1`` to run a subprocess smoke test (local only).
"""

from __future__ import annotations

import pytest

pytest.importorskip("jsonschema")

import json  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

from vdb_flow.llm.subprocess import SubprocessLlmProvider  # noqa: E402
from vdb_flow.metadata.resolver import (  # noqa: E402
    MetadataResolver,
    content_hash_from_text,
)


def _minimal_adr_body() -> str:
    """Short ADR-shaped markdown for tests that do not need the full obfuscated sample."""
    return """# ADR-005: Placeholder decision title

## Status

Accepted

## Context

Brief context for the decision.
"""


def _sample_adr_body() -> str:
    """Multi-section ADR with no vendor, product, person, or organization names."""
    return """# ADR-005: Adopt relational storage for authoritative state

## Status

Accepted

## Context

We require a relational store for transactional workloads. The existing
application tier already uses a stable driver stack; the secondary tier
will connect through read-only copies.

## Decision

We will standardize on a maintained major release of the selected engine
and apply schema changes through the repository migration workflow.

## Consequences

- Positive: Strong consistency, mature tooling.
- Negative: Operational overhead for backups and replication.
"""


class StubLlmProvider:
    """
    Deterministic stand-in for Claude / Anthropic / Codex.

    Implements the same contract as ``LlmProvider`` without network I/O.
    """

    def __init__(self, enrich: Optional[Dict[str, Any]] = None) -> None:
        self.calls: List[Tuple[str, Dict[str, Any]]] = []
        self._enrich = enrich or {
            "code_scope": ["rust", "cpp", "csharp"],
            "tags": ["database", "storage", "migration"],
        }

    def is_enabled(self) -> bool:
        return True

    def enrich_adr_metadata(
        self, markdown: str, draft: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.calls.append((markdown, dict(draft)))
        return dict(self._enrich)


def test_generated_adr_resolves_title_status_and_hash_without_llm(
    tmp_path: Path,
) -> None:
    """Rules-only path: title, status, adr_id, content_hash — no stub calls."""
    md = tmp_path / "adr-005-sample.md"
    body = _sample_adr_body()
    md.write_text(body, encoding="utf-8")

    r = MetadataResolver(enabled=True, llm_provider=None, use_llm_when_no_file=False)
    out = r.resolve(str(md), "docs/adr-005-sample.md", body)
    assert out is not None
    assert out["metadata_source"] == "generated"
    assert out["adr_id"] == "005"
    assert out["title"] == "ADR-005: Adopt relational storage for authoritative state"
    assert out["status"] == "Accepted"
    assert out["code_scope"] == ["general"]
    assert out["repo_type"] == ["all"]
    assert out["tags"] == []
    assert out["document_kind"] == "adr"
    assert out["content_hash"] == content_hash_from_text(body)


def test_generated_adr_with_stub_llm_merges_code_scope_and_tags(tmp_path: Path) -> None:
    """Stub LLM returns fixed JSON; merged metadata matches expectations."""
    md = tmp_path / "adr-005-sample.md"
    body = _minimal_adr_body()
    md.write_text(body, encoding="utf-8")

    stub = StubLlmProvider(
        {
            "code_scope": ["rust", "cpp", "yaml"],
            "tags": ["database", "storage"],
        }
    )
    r = MetadataResolver(enabled=True, llm_provider=stub, use_llm_when_no_file=True)
    out = r.resolve(str(md), "adr-005-sample.md", body)

    assert out is not None
    assert out["metadata_source"] == "merged"
    assert out["adr_id"] == "005"
    assert out["title"] == "ADR-005: Placeholder decision title"
    assert out["code_scope"] == ["rust", "cpp", "yaml"]
    assert out["repo_type"] == ["all"]
    assert out["tags"] == ["database", "storage"]
    assert out["document_kind"] == "adr"
    assert out["content_hash"] == content_hash_from_text(body)

    assert len(stub.calls) == 1
    seen_md, draft = stub.calls[0]
    assert "Brief context for the decision." in seen_md
    assert draft["adr_id"] == "005"
    assert draft["document_kind"] == "adr"
    assert "metadata_schema_version" in draft


def test_sidecar_skips_llm_stub(tmp_path: Path) -> None:
    """Valid ``.metadata.json`` wins; stub must not run."""
    md = tmp_path / "adr-005-sample.md"
    body = _minimal_adr_body()
    md.write_text(body, encoding="utf-8")
    side = tmp_path / "adr-005-sample.metadata.json"
    side.write_text(
        json.dumps(
            {
                "metadata_schema_version": "1",
                "document_kind": "adr",
                "adr_id": "005",
                "title": "Overridden title",
                "status": "Accepted",
                "code_scope": ["rust", "yaml"],
                "tags": ["from-json"],
            }
        ),
        encoding="utf-8",
    )

    stub = StubLlmProvider({"code_scope": ["should-not-appear"], "tags": ["x"]})
    r = MetadataResolver(enabled=True, llm_provider=stub, use_llm_when_no_file=True)
    out = r.resolve(str(md), "adr-005-sample.md", body)

    assert out is not None
    assert out["metadata_source"] == "file"
    assert out["title"] == "Overridden title"
    assert out["code_scope"] == ["rust", "yaml"]
    assert out["repo_type"] == ["all"]
    assert out["tags"] == ["from-json"]
    assert stub.calls == []


def test_sidecar_precedence_over_rules_title_and_adr_id(tmp_path: Path) -> None:
    """
    Sidecar JSON overrides rules-derived fields.

    Markdown H1 and filename would produce `adr_id` ``005`` and a long title; the
    file declares different canonical ``adr_id`` and ``title`` — those must win.
    """
    md = tmp_path / "adr-005-sample.md"
    body = _minimal_adr_body()
    md.write_text(body, encoding="utf-8")
    side = tmp_path / "adr-005-sample.metadata.json"
    side.write_text(
        json.dumps(
            {
                "metadata_schema_version": "1",
                "document_kind": "adr",
                "adr_id": "canonical-adr-005",
                "title": "Canonical title from metadata.json",
                "status": "Superseded",
                "code_scope": ["rust", "dockerfile"],
                "tags": ["canonical"],
            }
        ),
        encoding="utf-8",
    )

    stub = StubLlmProvider({"code_scope": ["cpp"], "tags": ["llm"]})
    r = MetadataResolver(enabled=True, llm_provider=stub, use_llm_when_no_file=True)
    out = r.resolve(str(md), "nested/adr-005-sample.md", body)

    assert out is not None
    assert out["metadata_source"] == "file"
    assert out["adr_id"] == "canonical-adr-005"
    assert out["title"] == "Canonical title from metadata.json"
    assert out["status"] == "Superseded"
    assert out["code_scope"] == ["rust", "dockerfile"]
    assert out["repo_type"] == ["all"]
    assert out["tags"] == ["canonical"]
    assert stub.calls == []


def test_sidecar_content_hash_always_from_markdown_not_sidecar_value(
    tmp_path: Path,
) -> None:
    """
    ``content_hash`` is always the hash of the current markdown body.

    Even if a sidecar sets a stale ``content_hash``, the resolver overwrites it
    with the computed value (so incremental load stays correct).
    """
    md = tmp_path / "adr-005-sample.md"
    body = _minimal_adr_body()
    md.write_text(body, encoding="utf-8")
    expected_hash = content_hash_from_text(body)
    side = tmp_path / "adr-005-sample.metadata.json"
    side.write_text(
        json.dumps(
            {
                "metadata_schema_version": "1",
                "document_kind": "adr",
                "adr_id": "005",
                "title": "T",
                "status": "Accepted",
                "content_hash": "0" * 64,
                "code_scope": [],
                "tags": [],
            }
        ),
        encoding="utf-8",
    )

    out = MetadataResolver(enabled=True, llm_provider=None).resolve(
        str(md), "adr-005-sample.md", body
    )
    assert out is not None
    assert out["content_hash"] == expected_hash
    assert out["content_hash"] != "0" * 64
    assert out["code_scope"] == ["general"]
    assert out["repo_type"] == ["all"]


def test_sidecar_metadata_file_path_relative_to_adr(tmp_path: Path) -> None:
    """``metadata_file`` points at the relative sidecar path next to the ADR."""
    md = tmp_path / "adr-005-sample.md"
    body = "# ADR-005\n\n## Status\nX\n"
    md.write_text(body, encoding="utf-8")
    side = tmp_path / "adr-005-sample.metadata.json"
    side.write_text(
        json.dumps(
            {
                "metadata_schema_version": "1",
                "adr_id": "005",
                "title": "T",
                "status": "Accepted",
                "code_scope": [],
                "tags": [],
            }
        ),
        encoding="utf-8",
    )

    out = MetadataResolver(enabled=True, llm_provider=None).resolve(
        str(md), "project/docs/adr/adr-005-sample.md", body
    )
    assert out is not None
    assert out["metadata_source"] == "file"
    assert out["metadata_file"] == "project/docs/adr/adr-005-sample.metadata.json"
    assert out["repo_type"] == ["all"]


def test_sidecar_can_set_repo_type_multi_value(tmp_path: Path) -> None:
    """Sidecar may scope ADR to specific repository kinds."""
    md = tmp_path / "adr-006.md"
    md.write_text("# T\n\n## Status\nX\n", encoding="utf-8")
    side = tmp_path / "adr-006.metadata.json"
    side.write_text(
        json.dumps(
            {
                "metadata_schema_version": "1",
                "document_kind": "adr",
                "adr_id": "006",
                "title": "T",
                "status": "Accepted",
                "code_scope": ["rust"],
                "repo_type": ["tool", "library"],
                "tags": [],
            }
        ),
        encoding="utf-8",
    )
    out = MetadataResolver(enabled=True, llm_provider=None).resolve(
        str(md), "adr-006.md", md.read_text(encoding="utf-8")
    )
    assert out is not None
    assert out["repo_type"] == ["tool", "library"]


@pytest.mark.skipif(
    os.environ.get("VDB_FLOW_TEST_SUBPROCESS_LLM") != "1",
    reason="Set VDB_FLOW_TEST_SUBPROCESS_LLM=1 to run subprocess LLM smoke test locally",
)
def test_subprocess_llm_provider_echo_json_roundtrip() -> None:
    """
    Smoke test: a subprocess prints JSON (simulates claude CLI output).

    Not run in default CI; use to validate SubprocessLlmProvider wiring on your machine.
    """
    code = (
        "import sys, json; "
        "d=json.load(sys.stdin); "
        "json.dump({'code_scope':['rust'], 'tags':['stub-tag']}, sys.stdout)"
    )
    provider = SubprocessLlmProvider([sys.executable, "-c", code], timeout=30)
    draft: Dict[str, Any] = {
        "metadata_schema_version": "1",
        "adr_id": "1",
        "title": "T",
        "status": "",
        "content_hash": "",
        "code_scope": [],
        "tags": [],
        "metadata_source": "generated",
        "metadata_file": None,
    }
    out = provider.enrich_adr_metadata("# Hello\n", draft)
    assert out["code_scope"] == ["rust"]
    assert out["tags"] == ["stub-tag"]
