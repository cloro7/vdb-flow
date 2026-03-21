"""Unit tests for InMemoryVectorDatabase (direct adapter coverage)."""

import pytest
from unittest.mock import Mock

from vdb_flow.database.adapters.inmemory import (
    InMemoryVectorDatabase,
    _create_inmemory_adapter,
)
from vdb_flow.database.port import (
    CollectionAlreadyExistsError,
    DatabaseOperationError,
    InvalidCollectionNameError,
    InvalidVectorSizeError,
)


@pytest.fixture
def db():
    return InMemoryVectorDatabase()


class TestFactory:
    def test_create_inmemory_adapter_returns_instance(self):
        client = _create_inmemory_adapter()
        assert isinstance(client, InMemoryVectorDatabase)


class TestCreateCollection:
    def test_duplicate_with_points_raises(self, db):
        db.create_collection("c", enable_hybrid=False, vector_size=4)
        db.upload_chunk("c", "x", "f.md", 1, lambda t: [0.0, 0.0, 0.0, 1.0])
        with pytest.raises(CollectionAlreadyExistsError):
            db.create_collection("c", enable_hybrid=False, vector_size=4)

    def test_invalid_name(self, db):
        with pytest.raises(InvalidCollectionNameError):
            db.create_collection("bad name", enable_hybrid=False)

    def test_invalid_vector_size(self, db):
        with pytest.raises(InvalidVectorSizeError):
            db.create_collection("ok", vector_size=0, enable_hybrid=False)


class TestUploadAndBatch:
    def test_batch_with_progress(self, db):
        db.create_collection("c", enable_hybrid=False, vector_size=2)
        prog = Mock()
        db.upload_chunks_batch(
            "c",
            [("a", "f", 1), ("b", "f", 2)],
            lambda t: [1.0, 0.0],
            progress_callback=prog,
        )
        assert prog.call_count == 2

    def test_batch_propagates_embedding_error(self, db):
        db.create_collection("c", enable_hybrid=False, vector_size=2)

        def bad_embed(_):
            raise RuntimeError("embed fail")

        with pytest.raises(DatabaseOperationError, match="Failed to upload chunk"):
            db.upload_chunks_batch(
                "c",
                [("a", "f", 1)],
                bad_embed,
            )


class TestSearchAndSimilarity:
    def test_search_empty_returns_empty(self, db):
        db.create_collection("c", enable_hybrid=False, vector_size=2)
        assert db.search("c", [0.0, 1.0], limit=5) == []

    def test_search_cosine_ordering(self, db):
        db.create_collection("c", distance_metric="Cosine", vector_size=3)
        db.upload_chunk("c", "a", "f", 1, lambda t: [1.0, 0.0, 0.0])
        db.upload_chunk("c", "b", "f", 2, lambda t: [0.0, 1.0, 0.0])
        out = db.search("c", [1.0, 0.0, 0.0], limit=2)
        assert len(out) == 2
        assert out[0]["score"] >= out[1]["score"]

    def test_search_dot_metric(self, db):
        db.create_collection("c", distance_metric="Dot", vector_size=2)
        db.upload_chunk("c", "a", "f", 1, lambda t: [2.0, 0.0])
        r = db.search("c", [1.0, 0.0], limit=1)
        assert len(r) == 1
        assert r[0]["score"] == pytest.approx(2.0)

    def test_search_euclid_metric(self, db):
        db.create_collection("c", distance_metric="Euclid", vector_size=2)
        db.upload_chunk("c", "a", "f", 1, lambda t: [0.0, 0.0])
        r = db.search("c", [0.0, 1.0], limit=1)
        assert len(r) == 1
        assert r[0]["score"] < 0  # negative distance as similarity

    def test_unsupported_metric_in_search_path(self, db):
        db.create_collection("c", enable_hybrid=False, vector_size=2)
        db._collections["c"]["config"]["distance_metric"] = "Weird"
        db.upload_chunk("c", "a", "f", 1, lambda t: [1.0, 0.0])
        with pytest.raises(DatabaseOperationError, match="Unsupported distance metric"):
            db.search("c", [1.0, 0.0], limit=1)
