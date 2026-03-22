"""Construct LLM provider from config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .claude_cli import ClaudeCliLlmProvider
from .none_provider import NoOpLlmProvider
from .subprocess import SubprocessLlmProvider

if TYPE_CHECKING:
    from ..config import Config


def create_llm_provider(config: "Config"):
    """
    Create provider from config.llm section.

    provider: none | subprocess | claude-cli
    """
    raw = getattr(config, "_config", {}).get("llm", {}) or {}
    provider = (raw.get("provider") or "none").strip().lower()
    if provider in ("none", "", "disabled", "off"):
        return NoOpLlmProvider()
    if provider == "subprocess":
        sub = raw.get("subprocess", {}) or {}
        cmd = sub.get("command")
        if not cmd or not isinstance(cmd, list):
            raise ValueError(
                'llm.provider is "subprocess" but llm.subprocess.command '
                "must be a non-empty list of strings"
            )
        env_raw = sub.get("env") or {}
        extra_env = {str(k): str(v) for k, v in env_raw.items()} if env_raw else None
        return SubprocessLlmProvider(
            [str(x) for x in cmd],
            timeout=int(sub.get("timeout", 300)),
            cwd=sub.get("cwd"),
            extra_env=extra_env,
        )
    if provider in ("claude-cli", "claude_cli"):
        cc = raw.get("claude_cli", {}) or {}
        cmd = cc.get("command")
        if not cmd or not isinstance(cmd, list):
            raise ValueError(
                'llm.provider is "claude-cli" but llm.claude_cli.command '
                'must be a non-empty list of strings (e.g. ["claude"] or a full path)'
            )
        env_raw = cc.get("env") or {}
        extra_env = {str(k): str(v) for k, v in env_raw.items()} if env_raw else None
        return ClaudeCliLlmProvider(
            [str(x) for x in cmd],
            timeout=int(cc.get("timeout", 300)),
            cwd=cc.get("cwd"),
            extra_env=extra_env,
        )
    raise ValueError(f"Unknown llm.provider: {provider!r}")
