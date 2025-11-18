"""Functional tests that exercise the CLI end-to-end using the in-memory adapter."""

import json
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import List, Tuple, Optional, Dict
from uuid import uuid4

import pytest
from unittest.mock import patch

from src.cli.main import main
from src.composition import reset_container


DEFAULT_ENV = {
    "VECTOR_DB_TYPE": "inmemory",  # Use in-memory adapter to avoid external deps
    "LOG_LEVEL": "INFO",
}


@pytest.fixture(autouse=True)
def reset_cli_container():
    """Ensure each test gets a fresh container/database."""
    reset_container()
    yield
    reset_container()


def _run_cli(
    args: List[str], extra_env: Optional[Dict[str, str]] = None
) -> Tuple[str, str]:
    """Invoke the CLI and capture stdout/stderr."""
    env = DEFAULT_ENV.copy()
    if extra_env:
        env.update(extra_env)

    stdout_buf = StringIO()
    stderr_buf = StringIO()

    with patch.dict(os.environ, env, clear=False):
        with patch.object(sys, "argv", ["vdb-flow", *args]):
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                try:
                    main()
                except SystemExit as exc:  # pragma: no cover - defensive
                    if exc.code not in (0, None):
                        raise

    return stdout_buf.getvalue().strip(), stderr_buf.getvalue()


def _generate_collection_name() -> str:
    return f"cli-test-{uuid4().hex[:8]}"


def test_cli_create_and_list_collections():
    """Creating a collection should be observable via list output."""
    collection = _generate_collection_name()

    stdout, stderr = _run_cli(["create", collection])
    payload = json.loads(stdout)
    assert payload["status"] == "ok"
    assert f"Collection created: name={collection}" in stderr

    stdout, stderr = _run_cli(["list"])
    collections = json.loads(stdout)
    names = [entry["name"] for entry in collections]
    assert collection in names
    assert "Found" in stderr


def test_cli_delete_removes_collection_from_list():
    """Deleting a collection should remove it from subsequent list output."""
    collection = _generate_collection_name()

    _run_cli(["create", collection])
    stdout, stderr = _run_cli(["delete", collection])
    payload = json.loads(stdout)
    assert payload["status"] == "ok"
    assert f"Collection deleted: name={collection}" in stderr

    stdout, _ = _run_cli(["list"])
    collections = json.loads(stdout)
    names = [entry["name"] for entry in collections]
    assert collection not in names
