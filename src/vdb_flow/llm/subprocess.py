"""Run an external CLI (e.g. Claude) via subprocess; stdout must be JSON."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

from ..metadata.code_scope import ALLOWED_CODE_SCOPES

logger = logging.getLogger(__name__)


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


class SubprocessLlmProvider:
    """
    Invoke a user-configured command; pass a JSON task on stdin; parse JSON from stdout.

    vdb-flow does not read Claude or other vendor config files — the command must
    embed any CLI flags the user needs.
    """

    def __init__(
        self,
        command: List[str],
        *,
        timeout: int = 300,
        cwd: Optional[str] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ):
        """Configure subprocess argv, timeout, cwd, and extra env."""
        if not command:
            raise ValueError("llm subprocess command must be non-empty")
        self.command = command
        self.timeout = timeout
        self.cwd = cwd
        self.extra_env = dict(extra_env) if extra_env else {}

    def is_enabled(self) -> bool:
        """Return True (provider is active when configured)."""
        return True

    def enrich_adr_metadata(
        self, markdown: str, draft: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send JSON task on stdin; parse ``code_scope`` / ``tags`` from stdout."""
        payload = {
            "task": "adr_metadata_enrich",
            "markdown": markdown,
            "draft": draft,
            "instruction": (
                "Respond with JSON only: an object with optional keys "
                '"code_scope" (non-empty array) and "tags" (array of strings). '
                "For code_scope you MUST use only these lowercase tokens (one or more): "
                + ", ".join(ALLOWED_CODE_SCOPES)
                + '. If no specific technology applies, use ["general"] only.'
            ),
        }
        stdin = json.dumps(payload, ensure_ascii=False)
        env = os.environ.copy()
        env.update(self.extra_env)
        try:
            proc = subprocess.run(
                self.command,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"LLM subprocess timed out after {self.timeout}s") from e
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(
                f"LLM subprocess failed (exit {proc.returncode}): {err[:2000]}"
            )
        raw = _strip_json_fence(proc.stdout or "")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM output must be a JSON object")
        # Only pass through known enrichment keys
        out: Dict[str, Any] = {}
        if "code_scope" in data:
            out["code_scope"] = data["code_scope"]
        if "tags" in data:
            out["tags"] = data["tags"]
        return out
