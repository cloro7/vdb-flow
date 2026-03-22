"""Unit tests for ``repo_type`` normalization."""

from __future__ import annotations

import pytest

pytest.importorskip("jsonschema")

from vdb_flow.metadata.repo_type import (  # noqa: E402
    apply_repo_type_normalization,
    normalize_repo_type,
)


def test_normalize_defaults_to_all_when_missing_or_empty() -> None:
    assert normalize_repo_type(None) == ["all"]
    assert normalize_repo_type([]) == ["all"]
    assert normalize_repo_type("unit") == ["all"]
    assert normalize_repo_type({}) == ["all"]


def test_normalize_preserves_specific_types() -> None:
    assert normalize_repo_type(["unit"]) == ["unit"]
    assert normalize_repo_type(["tool", "library"]) == ["tool", "library"]
    assert normalize_repo_type(["LIBRARY", " Tool "]) == ["library", "tool"]


def test_normalize_dedupes_preserves_order() -> None:
    assert normalize_repo_type(["unit", "unit", "tool"]) == ["unit", "tool"]


def test_normalize_all_collapses_with_others() -> None:
    assert normalize_repo_type(["all"]) == ["all"]
    assert normalize_repo_type(["library", "all", "unit"]) == ["all"]


def test_normalize_drops_unknown_entries() -> None:
    assert normalize_repo_type(["nope", "bad", "unit"]) == ["unit"]
    assert normalize_repo_type(["nope"]) == ["all"]


def test_apply_repo_type_normalization_mutates_dict() -> None:
    m: dict = {}
    apply_repo_type_normalization(m)
    assert m == {"repo_type": ["all"]}
