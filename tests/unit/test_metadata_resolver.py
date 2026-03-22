"""Unit tests for ADR metadata resolution."""

import json

from vdb_flow.metadata.rules import adr_id_from_stem, extract_title_from_markdown
from vdb_flow.metadata.resolver import MetadataResolver, content_hash_from_text


def test_extract_title():
    assert extract_title_from_markdown("# Hello\n\nbody") == "Hello"


def test_extract_title_prefers_h1_not_first_line():
    body = "A long opening paragraph that is not a heading.\n\n# Real title\n\nMore."
    assert extract_title_from_markdown(body, stem="x") == "Real title"


def test_extract_title_skips_yaml_frontmatter():
    body = "---\ndate: 2020\n---\n\n# From frontmatter doc\n\nText."
    assert extract_title_from_markdown(body) == "From frontmatter doc"


def test_extract_title_does_not_use_entire_file_as_one_line():
    blob = "x" * 5000
    assert extract_title_from_markdown(blob, stem="adr-042-widget") == "adr 042 widget"


def test_extract_title_long_first_line_falls_back_to_stem():
    first = "Short" * 80
    body = first + "\n\n## Status\nx\n"
    assert len(first) > 200
    assert extract_title_from_markdown(body, stem="my-adr") == "my adr"


def test_adr_id_from_stem():
    assert adr_id_from_stem("adr-001-foo") == "001"
    assert adr_id_from_stem("plain-name") == "plain-name"


def test_content_hash_stable():
    h1 = content_hash_from_text("a\n")
    h2 = content_hash_from_text("a\n")
    assert h1 == h2
    assert len(h1) == 64


def test_sidecar_precedence(tmp_path):
    md = tmp_path / "adr-001-x.md"
    md.write_text("# Title\n\n## Status\nProposed\n", encoding="utf-8")
    side = tmp_path / "adr-001-x.metadata.json"
    side.write_text(
        json.dumps(
            {
                "metadata_schema_version": "1",
                "document_kind": "adr",
                "adr_id": "001",
                "title": "From JSON",
                "status": "Accepted",
                "code_scope": ["rust"],
                "tags": ["t"],
            }
        ),
        encoding="utf-8",
    )
    r = MetadataResolver(enabled=True, llm_provider=None)
    out = r.resolve(str(md), "adr-001-x.md", md.read_text(encoding="utf-8"))
    assert out is not None
    assert out["metadata_source"] == "file"
    assert out["title"] == "From JSON"
    assert out["code_scope"] == ["rust"]
    assert out["repo_type"] == ["all"]
    assert out["document_kind"] == "adr"


def test_rules_only_no_file(tmp_path):
    md = tmp_path / "adr-002-y.md"
    md.write_text("# My ADR\n\n## Status\nDraft\n", encoding="utf-8")
    r = MetadataResolver(enabled=True, llm_provider=None)
    out = r.resolve(str(md), "adr-002-y.md", md.read_text(encoding="utf-8"))
    assert out is not None
    assert out["metadata_source"] == "generated"
    assert out["adr_id"] == "002"
    assert out["document_kind"] == "adr"
    assert "content_hash" in out and len(out["content_hash"]) == 64
    assert out["repo_type"] == ["all"]
