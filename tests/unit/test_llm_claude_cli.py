"""Tests for Claude Code CLI LLM provider (mocked subprocess)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from vdb_flow.config import Config
from vdb_flow.llm.claude_cli import (
    ClaudeCliLlmProvider,
    _format_cli_error,
    _sanitize_anthropic_prompt_fragments,
    build_claude_cli_prompt,
)
from vdb_flow.llm.factory import create_llm_provider
from vdb_flow.metadata.code_scope import ALLOWED_CODE_SCOPES


def test_sanitize_breaks_reserved_anthropic_billing_header_token() -> None:
    raw = "See header x-anthropic-billing-header in logs."
    out = _sanitize_anthropic_prompt_fragments(raw)
    assert "x-anthropic-billing-header" not in out
    assert "[omitted reserved name]" in out
    assert "in logs" in out


def test_sanitize_reserved_token_case_insensitive() -> None:
    raw = "X-ANTHROPIC-BILLING-HEADER"
    out = _sanitize_anthropic_prompt_fragments(raw)
    assert "x-anthropic-billing-header" not in out.lower()
    assert "[omitted reserved name]" in out


def test_build_claude_cli_prompt_strips_forbidden_substring_from_adr_text() -> None:
    md = "# ADR\n\nMention x-anthropic-billing-header in error docs."
    p = build_claude_cli_prompt(md, {"adr_id": "1", "title": "T"})
    assert "x-anthropic-billing-header" not in p
    assert "error docs" in p


def test_build_claude_cli_prompt_includes_markdown_draft_and_vocab() -> None:
    md = "# ADR-1\n\nBody."
    draft = {"adr_id": "1", "title": "T", "metadata_schema_version": "1"}
    p = build_claude_cli_prompt(md, draft)
    assert md in p
    assert '"adr_id"' in p and "1" in p
    for token in ALLOWED_CODE_SCOPES:
        assert token in p


def test_claude_cli_enrich_parses_json_stdout() -> None:
    out_json = json.dumps({"code_scope": ["rust", "yaml"], "tags": ["a", "b"]})
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = out_json
    proc.stderr = ""

    p = ClaudeCliLlmProvider(["claude"], timeout=30)
    with patch("vdb_flow.llm.claude_cli.subprocess.run", return_value=proc) as run:
        got = p.enrich_adr_metadata(
            "# x",
            {"adr_id": "1", "title": "T"},
        )
    assert got == {"code_scope": ["rust", "yaml"], "tags": ["a", "b"]}
    run.assert_called_once()
    args, kwargs = run.call_args
    argv = args[0]
    assert argv == ["claude", "-p", "--output-format", "json"]
    assert "# x" in (kwargs.get("input") or "")


def test_claude_cli_enrich_unwraps_result_wrapper() -> None:
    inner = json.dumps({"code_scope": ["general"], "tags": ["t"]})
    wrapped = json.dumps({"result": inner, "session_id": "x"})
    proc = MagicMock(returncode=0, stdout=wrapped, stderr="")

    p = ClaudeCliLlmProvider(["/opt/bin/claude"])
    with patch("vdb_flow.llm.claude_cli.subprocess.run", return_value=proc):
        got = p.enrich_adr_metadata("x", {"adr_id": "1", "title": "T"})
    assert got["code_scope"] == ["general"]
    assert got["tags"] == ["t"]


def test_format_cli_error_readablestream_hints_node_18() -> None:
    raw = "ReferenceError: ReadableStream is not defined\n    at cli.js:1"
    out = _format_cli_error(raw, "")
    assert "Node.js 18" in out
    assert "ReadableStream" in out


def test_claude_cli_raises_on_nonzero_exit() -> None:
    proc = MagicMock(returncode=1, stdout="", stderr="boom")
    p = ClaudeCliLlmProvider(["claude"])
    with patch("vdb_flow.llm.claude_cli.subprocess.run", return_value=proc):
        with pytest.raises(RuntimeError, match="Claude CLI failed"):
            p.enrich_adr_metadata("x", {})


def test_factory_claude_cli_provider() -> None:
    cfg = Config(config_path=None)
    cfg._config["llm"] = {
        "provider": "claude-cli",
        "claude_cli": {
            "command": ["claude"],
            "timeout": 60,
            "cwd": None,
            "env": {},
        },
    }
    prov = create_llm_provider(cfg)
    assert isinstance(prov, ClaudeCliLlmProvider)
    assert prov.command == ["claude"]
    assert prov.timeout == 60


def test_factory_claude_cli_requires_command() -> None:
    cfg = Config(config_path=None)
    cfg._config["llm"] = {"provider": "claude-cli", "claude_cli": {"command": []}}
    with pytest.raises(ValueError, match="claude_cli.command"):
        create_llm_provider(cfg)


def test_factory_accepts_claude_cli_alias() -> None:
    cfg = Config(config_path=None)
    cfg._config["llm"] = {
        "provider": "claude_cli",
        "claude_cli": {"command": ["claude"]},
    }
    prov = create_llm_provider(cfg)
    assert isinstance(prov, ClaudeCliLlmProvider)
