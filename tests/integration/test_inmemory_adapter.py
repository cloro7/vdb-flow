"""Integration tests for in-memory vector database adapter."""

import pytest
import tempfile
from pathlib import Path

from src.database import create_vector_database, get_available_adapters
from src.services.collection import CollectionService
from src.services.embedding import get_embedding


@pytest.fixture
def inmemory_client():
    """Create an in-memory database client."""
    return create_vector_database("inmemory")


@pytest.fixture
def collection_service(inmemory_client):
    """Create a CollectionService with in-memory database."""
    return CollectionService(
        db_client=inmemory_client,
        embedding_func=get_embedding,
    )


class TestInMemoryAdapterRegistry:
    """Test that the in-memory adapter is properly registered."""

    def test_adapter_is_registered(self):
        """Test that in-memory adapter is in the registry."""
        adapters = get_available_adapters()
        assert "inmemory" in adapters
        assert "qdrant" in adapters

    def test_create_inmemory_adapter(self):
        """Test creating an in-memory adapter."""
        client = create_vector_database("inmemory")
        assert client is not None
        assert hasattr(client, "create_collection")
        assert hasattr(client, "list_collections")


class TestInMemoryCollectionOperations:
    """Test collection operations with in-memory adapter."""

    def test_create_collection(self, inmemory_client):
        """Test creating a collection."""
        collection_name = "test-collection"
        result = inmemory_client.create_collection(
            collection_name, enable_hybrid=False, vector_size=768
        )
        assert result["status"] == "ok"
        assert result["result"]["points_count"] == 0

    def test_create_collection_already_exists(self, inmemory_client):
        """Test creating a collection that already exists."""
        collection_name = "test-collection"
        inmemory_client.create_collection(collection_name, enable_hybrid=False)

        # Should raise CollectionAlreadyExistsError if collection has points
        # But since it's empty, it should succeed (idempotent create)
        result = inmemory_client.create_collection(collection_name, enable_hybrid=False)
        assert result["status"] == "ok"

    def test_list_collections(self, inmemory_client):
        """Test listing collections."""
        # Initially empty
        collections = inmemory_client.list_collections()
        assert isinstance(collections, list)

        # Create a collection
        inmemory_client.create_collection("test-1", enable_hybrid=False)
        inmemory_client.create_collection("test-2", enable_hybrid=False)

        collections = inmemory_client.list_collections()
        assert len(collections) == 2
        collection_names = [c["name"] for c in collections]
        assert "test-1" in collection_names
        assert "test-2" in collection_names

    def test_get_collection_info(self, inmemory_client):
        """Test getting collection information."""
        collection_name = "test-collection"
        inmemory_client.create_collection(
            collection_name, enable_hybrid=False, vector_size=768
        )

        info = inmemory_client.get_collection_info(collection_name)
        assert info["status"] == "ok"
        assert info["result"]["points_count"] == 0
        assert info["result"]["config"]["params"]["vectors"]["size"] == 768

    def test_get_collection_info_not_found(self, inmemory_client):
        """Test getting info for non-existent collection."""
        from src.database import CollectionNotFoundError

        with pytest.raises(CollectionNotFoundError):
            inmemory_client.get_collection_info("non-existent")

    def test_delete_collection(self, inmemory_client):
        """Test deleting a collection."""
        collection_name = "test-collection"
        inmemory_client.create_collection(collection_name, enable_hybrid=False)
        inmemory_client.delete_collection(collection_name)

        # Should raise error when trying to get info
        from src.database import CollectionNotFoundError

        with pytest.raises(CollectionNotFoundError):
            inmemory_client.get_collection_info(collection_name)

    def test_delete_collection_not_found(self, inmemory_client):
        """Test deleting a non-existent collection."""
        from src.database import CollectionNotFoundError

        with pytest.raises(CollectionNotFoundError):
            inmemory_client.delete_collection("non-existent")

    def test_clear_collection(self, inmemory_client):
        """Test clearing a collection."""
        collection_name = "test-collection"
        inmemory_client.create_collection(collection_name, enable_hybrid=False)

        # Upload a chunk
        inmemory_client.upload_chunk(
            collection_name,
            "test chunk",
            "test.md",
            1,
            lambda text: [0.1] * 768,
        )

        # Verify it has points
        info = inmemory_client.get_collection_info(collection_name)
        assert info["result"]["points_count"] == 1

        # Clear collection
        inmemory_client.clear_collection(collection_name)

        # Verify it's empty
        info = inmemory_client.get_collection_info(collection_name)
        assert info["result"]["points_count"] == 0

    def test_clear_collection_not_found(self, inmemory_client):
        """Test clearing a non-existent collection."""
        from src.database import CollectionNotFoundError

        with pytest.raises(CollectionNotFoundError):
            inmemory_client.clear_collection("non-existent")


class TestInMemoryCollectionService:
    """Test CollectionService with in-memory adapter."""

    def test_create_collection_via_service(self, collection_service):
        """Test creating a collection via CollectionService."""
        collection_name = "test-collection"
        collection_service.create_collection(collection_name, enable_hybrid=False)

        info = collection_service.get_collection_info(collection_name)
        assert info["result"]["points_count"] == 0

    def test_load_collection(self, collection_service):
        """Test loading ADR files into a collection."""
        collection_name = "test-collection"
        collection_service.create_collection(collection_name, enable_hybrid=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test ADR file
            adr_file = Path(tmpdir) / "adr-001.md"
            adr_file.write_text(
                """# ADR-001: Test Decision

## Status
Accepted

## Context
This is a test ADR.

## Decision
We will test the in-memory adapter.

## Consequences
- Positive: No external dependencies
- Negative: Data is not persisted
"""
            )

            # Load collection
            collection_service.load_collection(collection_name, tmpdir)

            # Verify data was loaded
            info = collection_service.get_collection_info(collection_name)
            assert info["result"]["points_count"] > 0

    def test_search_after_load(self, collection_service):
        """Test searching after loading data."""
        collection_name = "test-collection"
        collection_service.create_collection(collection_name, enable_hybrid=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test ADR file
            adr_file = Path(tmpdir) / "adr-001.md"
            adr_file.write_text(
                """# ADR-001: Use In-Memory Database

## Status
Accepted

## Context
We need a test database.

## Decision
Use in-memory adapter for testing.

## Consequences
- Positive: Fast, no setup required
- Negative: Not persistent
"""
            )

            # Load collection
            collection_service.load_collection(collection_name, tmpdir)

            # Perform search
            query_vector = get_embedding("test database")
            results = collection_service.db_client.search(
                collection_name, query_vector, limit=5
            )

            assert len(results) > 0
            assert "score" in results[0]
            assert "payload" in results[0]

    def test_delete_collection_via_service(self, collection_service):
        """Test deleting a collection via CollectionService."""
        collection_name = "test-collection"
        collection_service.create_collection(collection_name, enable_hybrid=False)
        collection_service.delete_collection(collection_name)

        # Should raise error
        from src.database import CollectionNotFoundError

        with pytest.raises(CollectionNotFoundError):
            collection_service.get_collection_info(collection_name)

    def test_list_collections_via_service(self, collection_service):
        """Test listing collections via CollectionService."""
        collection_service.create_collection("test-1", enable_hybrid=False)
        collection_service.create_collection("test-2", enable_hybrid=False)

        collections = collection_service.list_collections()
        assert len(collections) == 2
        collection_names = [c["name"] for c in collections]
        assert "test-1" in collection_names
        assert "test-2" in collection_names


class TestInMemoryAdapterCompatibility:
    """Test that in-memory adapter behaves like Qdrant adapter for common operations."""

    def test_same_interface(self, inmemory_client):
        """Test that in-memory adapter implements the same interface."""
        # All methods should exist
        assert hasattr(inmemory_client, "create_collection")
        assert hasattr(inmemory_client, "delete_collection")
        assert hasattr(inmemory_client, "clear_collection")
        assert hasattr(inmemory_client, "get_collection_info")
        assert hasattr(inmemory_client, "list_collections")
        assert hasattr(inmemory_client, "upload_chunk")
        assert hasattr(inmemory_client, "upload_chunks_batch")
        assert hasattr(inmemory_client, "search")

    def test_same_exceptions(self, inmemory_client):
        """Test that in-memory adapter raises the same exceptions."""
        from src.database import (
            CollectionNotFoundError,
            InvalidCollectionNameError,
            InvalidVectorSizeError,
        )

        # CollectionNotFoundError
        with pytest.raises(CollectionNotFoundError):
            inmemory_client.get_collection_info("non-existent")

        # InvalidCollectionNameError
        with pytest.raises(InvalidCollectionNameError):
            inmemory_client.create_collection("invalid collection name")

        # InvalidVectorSizeError
        with pytest.raises(InvalidVectorSizeError):
            inmemory_client.create_collection("test", vector_size=0)

    def test_vector_size_validation(self, inmemory_client):
        """Test that vector size is validated consistently."""
        collection_name = "test-collection"
        inmemory_client.create_collection(
            collection_name, vector_size=768, enable_hybrid=False
        )

        # Upload with correct size should work
        inmemory_client.upload_chunk(
            collection_name,
            "test",
            "test.md",
            1,
            lambda text: [0.1] * 768,
        )

        # Upload with wrong size should fail
        from src.database import DatabaseOperationError

        with pytest.raises(DatabaseOperationError, match="Vector size mismatch"):
            inmemory_client.upload_chunk(
                collection_name,
                "test",
                "test.md",
                2,
                lambda text: [0.1] * 512,  # Wrong size
            )
