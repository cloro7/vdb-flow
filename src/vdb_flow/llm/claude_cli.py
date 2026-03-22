"""Claude Code CLI: non-interactive ``-p`` prompt built in code; stdout must be JSON."""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

from .subprocess import _strip_json_fence
from ..metadata.code_scope import ALLOWED_CODE_SCOPES

# Fixed flags (not user-configurable): headless mode + JSON on stdout. Prompt is sent on stdin
# so large ADRs are not passed as a single argv (ARG_MAX / CLI limits; Node has had issues).
_CLAUDE_CLI_FIXED_ARGS = ("-p", "--output-format", "json")


def _format_cli_error(stderr: str, stdout: str) -> str:
    err = (stderr or stdout or "").strip()
    if (
        "ReadableStream is not defined" in err
        or "ReferenceError: ReadableStream" in err
    ):
        return (
            "Claude Code requires Node.js 18+ (global ReadableStream). Node 16 is unsupported. "
            "Example: nvm install 20 && nvm use 20, then verify with `node -v` and `claude -p hi`. "
            "Original (truncated): " + err[:1200]
        )
    if len(err) > 600 and ("exports" in err or "function(" in err or "=>" in err[:200]):
        return (
            "Claude CLI failed; stderr looks like minified JS (often Node too old or a broken "
            "CLI install). Use Node.js 18+ for @anthropic-ai/claude-code, run `claude -p hi` "
            "manually, and ensure auth works. First 400 chars: " + err[:400]
        )
    return err[:2000]


# Substrings Anthropic's API rejects anywhere in the combined prompt (400 reserved keyword).
# Replace the whole token: some transports or Claude Code may strip U+200B before the API.
_ANTHROPIC_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = ("x-anthropic-billing-header",)
# Must not contain any forbidden substring.
_ANTHROPIC_FORBIDDEN_REPLACEMENT = "[omitted reserved name]"


def _sanitize_anthropic_prompt_fragments(text: str) -> str:
    """Strip or replace substrings Anthropic's API rejects in prompts (400 reserved keyword)."""
    out = text
    for frag in _ANTHROPIC_FORBIDDEN_SUBSTRINGS:
        pattern = re.compile(re.escape(frag), re.IGNORECASE)
        out = pattern.sub(_ANTHROPIC_FORBIDDEN_REPLACEMENT, out)
    return out


def _enrichment_instruction() -> str:
    scopes = ", ".join(ALLOWED_CODE_SCOPES)
    return (
        "Respond with a single JSON object only (no markdown, no commentary). "
        "Optional keys: "
        '"code_scope" (array of one or more strings) and "tags" (array of strings). '
        f"Each code_scope entry MUST be one of these lowercase tokens: {scopes}. "
        'If no specific technology applies, use "general" alone in code_scope.'
    )


def build_claude_cli_prompt(markdown: str, draft: Dict[str, Any]) -> str:
    """
    Full prompt for headless Claude — kept in application code, not user config.

    The provider passes this string on **stdin** to ``claude -p --output-format json`` (see
    Anthropic headless docs: piped input with ``-p``).
    """
    draft_json = json.dumps(draft, ensure_ascii=False, indent=2)
    raw = (
        "You help enrich Architecture Decision Record (ADR) metadata for a vector database.\n\n"
        f"{_enrichment_instruction()}\n\n"
        "--- Draft metadata from rules (JSON) ---\n"
        f"{draft_json}\n\n"
        "--- ADR markdown ---\n"
        f"{markdown.strip()}\n"
    )
    return _sanitize_anthropic_prompt_fragments(raw)


class ClaudeCliLlmProvider:
    r"""
    Run the Claude Code CLI in non-interactive mode.

    Invokes ``<command> -p --output-format json`` with the **prompt on stdin** (not as a giant
    ``-p`` argv). ``command`` is the argv prefix (e.g. ``[\"claude\"]`` or a full path).
    """

    def __init__(
        self,
        command: List[str],
        *,
        timeout: int = 300,
        cwd: Optional[str] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ):
        """Build provider; ``command`` is argv before fixed ``-p`` / ``--output-format json``."""
        if not command or not isinstance(command, list):
            raise ValueError("claude_cli.command must be a non-empty list of strings")
        self.command = [str(x) for x in command]
        self.timeout = timeout
        self.cwd = cwd
        self.extra_env = dict(extra_env) if extra_env else {}

    def is_enabled(self) -> bool:
        """Return True (provider is active when configured)."""
        return True

    def enrich_adr_metadata(
        self, markdown: str, draft: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run CLI with prompt on stdin; return ``code_scope`` / ``tags`` from JSON stdout."""
        prompt = build_claude_cli_prompt(markdown, draft)
        argv = list(self.command) + list(_CLAUDE_CLI_FIXED_ARGS)
        env = os.environ.copy()
        env.update(self.extra_env)
        try:
            proc = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Claude CLI timed out after {self.timeout}s") from e
        if proc.returncode != 0:
            err = _format_cli_error(proc.stderr or "", proc.stdout or "")
            raise RuntimeError(f"Claude CLI failed (exit {proc.returncode}): {err}")
        raw = proc.stdout or ""
        data = self._parse_stdout_json(raw)
        if not isinstance(data, dict):
            raise ValueError("Claude CLI output must be a JSON object")
        out: Dict[str, Any] = {}
        if "code_scope" in data:
            out["code_scope"] = data["code_scope"]
        if "tags" in data:
            out["tags"] = data["tags"]
        return out

    def _parse_stdout_json(self, raw: str, _depth: int = 0) -> Any:
        """Parse JSON from stdout; handle optional ``` fences and simple wrappers."""
        if _depth > 5:
            raise ValueError("Could not find enrichment JSON in Claude CLI output")
        text = _strip_json_fence(raw.strip())
        data = json.loads(text)
        if isinstance(data, dict) and "code_scope" not in data and "tags" not in data:
            so = data.get("structured_output")
            if isinstance(so, dict) and ("code_scope" in so or "tags" in so):
                return so
            for key in ("result", "output", "response", "text"):
                inner = data.get(key)
                if isinstance(inner, str) and inner.strip():
                    try:
                        return self._parse_stdout_json(inner, _depth + 1)
                    except (json.JSONDecodeError, ValueError):
                        continue
        return data
