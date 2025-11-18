"""Integration tests for collection service."""

import os
import tempfile
import pytest
from pathlib import Path

from src.database import VectorDatabase, create_vector_database
from src.database.adapters.qdrant import QdrantCollectionNotFoundError
from src.services.collection import CollectionService


@pytest.fixture
def test_adr_dir():
    """Create a temporary directory with test ADR files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test ADR file
        adr_file = Path(tmpdir) / "adr-001-test.md"
        adr_file.write_text(
            """# ADR-001: Test Decision

## Status
Accepted

## Context
This is a test architecture decision record for integration testing.

## Decision
We will use this ADR for testing purposes.

## Consequences
- Positive: Allows us to test the collection service
- Negative: None, it's just a test
"""
        )
        yield tmpdir


@pytest.fixture
def qdrant_client() -> VectorDatabase:
    """Create a Qdrant client for testing."""
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    return create_vector_database(db_type="qdrant", qdrant_url=qdrant_url)


@pytest.fixture
def collection_service(qdrant_client):
    """Create a collection service for testing."""
    return CollectionService(qdrant_client)


@pytest.fixture
def test_collection(qdrant_client):
    """Create a test collection and clean it up after."""
    collection_name = "test-integration-collection"
    # Clean up if it exists
    try:
        qdrant_client.delete_collection(collection_name)
    except Exception:
        pass

    # Create the collection
    qdrant_client.create_collection(collection_name, enable_hybrid=False)

    yield collection_name

    # Clean up
    try:
        qdrant_client.delete_collection(collection_name)
    except Exception:
        pass


def test_create_collection(collection_service):
    """Test that create_collection can create a collection."""
    collection_name = "test-integration-collection"
    collection_service.create_collection(collection_name, enable_hybrid=False)
    collection_info = collection_service.get_collection_info(collection_name)
    assert collection_info is not None
    assert collection_info.get("status") == "ok"
    assert collection_info.get("result", {}).get("points_count") == 0
    # Clean up
    collection_service.delete_collection(collection_name)


def test_delete_collection(collection_service, test_collection):
    """Test that delete_collection can delete a collection."""
    # Verify collection exists before deletion
    collection_info = collection_service.get_collection_info(test_collection)
    assert collection_info is not None
    assert collection_info.get("status") == "ok"

    # Delete the collection
    collection_service.delete_collection(test_collection)

    # Verify collection no longer exists
    with pytest.raises(QdrantCollectionNotFoundError):
        collection_service.get_collection_info(test_collection)


def test_get_collection_info_nonexistent(collection_service):
    """Test that get_collection_info raises QdrantCollectionNotFoundError for non-existent collection."""
    non_existent_collection = "non-existent-collection-12345"
    with pytest.raises(QdrantCollectionNotFoundError):
        collection_service.get_collection_info(non_existent_collection)


def test_load_collection(collection_service, test_collection, test_adr_dir):
    """Test that load_collection can load ADR files."""
    # Load the collection
    collection_service.load_collection(test_collection, test_adr_dir)

    # Verify collection exists and has data
    collection_info = collection_service.get_collection_info(test_collection)
    assert collection_info is not None

    # Check that points were uploaded (collection should have points count > 0)
    result = collection_info.get("result", {})
    points_count = result.get("points_count", 0)
    assert points_count > 0, "Collection should have uploaded points"


def test_load_collection_with_multiple_files(collection_service, qdrant_client):
    """Test loading multiple ADR files with realistic content."""
    collection_name = "test-multi-file-collection"

    # Clean up if exists
    try:
        qdrant_client.delete_collection(collection_name)
    except Exception:
        pass

    # Create collection
    collection_service.create_collection(collection_name, enable_hybrid=False)

    try:
        # Create temporary directory with multiple ADR files
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple ADR files with different content
            adr_files = [
                (
                    "adr-001-use-vector-database.md",
                    """# ADR-001: Use Vector Database for ADR Storage

## Status
Accepted

## Context
We need to store and search through Architecture Decision Records (ADRs) efficiently. Traditional databases are not optimized for semantic search.

## Decision
We will use a vector database (Qdrant) to store ADRs with embeddings for semantic search capabilities.

## Consequences
- Positive: Fast semantic search, can find similar decisions
- Negative: Requires embedding generation, additional infrastructure
""",
                ),
                (
                    "adr-002-implement-hybrid-search.md",
                    """# ADR-002: Implement Hybrid Search

## Status
Accepted

## Context
Semantic search alone may not always find exact keyword matches. Users might search for specific terms.

## Decision
We will implement hybrid search combining semantic (vector) and keyword (BM25) search for better results.

## Consequences
- Positive: Better search results, handles both semantic and keyword queries
- Negative: More complex implementation, requires sparse vectors
""",
                ),
                (
                    "adr-003-use-ollama-embeddings.md",
                    """# ADR-003: Use Ollama for Embeddings

## Status
Accepted

## Context
We need to generate embeddings for text chunks. Cloud embedding services have cost and latency concerns.

## Decision
We will use Ollama with nomic-embed-text model for local embedding generation.

## Consequences
- Positive: No API costs, runs locally, good performance
- Negative: Requires local Ollama instance, model management
""",
                ),
            ]

            # Write all ADR files
            for filename, content in adr_files:
                adr_file = Path(tmpdir) / filename
                adr_file.write_text(content)

            # Load the collection
            collection_service.load_collection(collection_name, tmpdir)

            # Verify collection has data
            collection_info = collection_service.get_collection_info(collection_name)
            assert collection_info is not None
            result = collection_info.get("result", {})
            points_count = result.get("points_count", 0)
            assert points_count > 0, "Collection should have uploaded points"

            # Verify we can search the loaded data
            # Get a sample embedding to test search
            from src.services.embedding import get_embedding

            test_query = "vector database search"
            query_vector = get_embedding(test_query)

            # Perform a search
            search_results = qdrant_client.search(
                collection_name, query_vector, limit=5
            )
            assert len(search_results) > 0, "Search should return results"

            # Verify search results contain expected content
            # At least one result should mention vector database or ADR
            result_texts = [
                result.get("payload", {}).get("chunk_text", "").lower()
                for result in search_results
            ]
            assert any(
                "vector" in text or "adr" in text or "database" in text
                for text in result_texts
            ), "Search results should contain relevant content"

            # Verify points have correct metadata
            for result in search_results[:3]:  # Check first 3 results
                payload = result.get("payload", {})
                assert (
                    "source_file" in payload
                ), "Points should have source_file metadata"
                assert "chunk_id" in payload, "Points should have chunk_id metadata"
                assert "chunk_text" in payload, "Points should have chunk_text metadata"
                # Verify source_file is one of our ADR files
                source_file = payload.get("source_file", "")
                assert any(
                    adr_file[0] in source_file for adr_file in adr_files
                ), f"Source file {source_file} should be one of the loaded ADR files"
    finally:
        # Clean up
        try:
            qdrant_client.delete_collection(collection_name)
        except Exception:
            pass


def test_list_collections(collection_service, test_collection):
    """Test that list_collections can list collections."""
    collections = collection_service.list_collections()
    assert isinstance(collections, list), "list_collections should return a list"
    assert len(collections) > 0, "Should have at least one collection"
    assert test_collection in [
        col.get("name") for col in collections
    ], f"Collection {test_collection} should be in the list"


def test_load_non_existent_collection(collection_service, test_adr_dir):
    """Test that load_collection raises ValueError for non-existent collection."""
    non_existent_collection = "non-existent-collection-12345"
    with pytest.raises(
        ValueError,
        match=f"Collection '{non_existent_collection}' does not exist. Please create it first using the 'create' command.",
    ):
        collection_service.load_collection(non_existent_collection, test_adr_dir)


def test_create_collection_invalid_name(collection_service):
    """Test that create_collection raises ValueError for invalid collection name."""
    with pytest.raises(
        ValueError, match="Invalid collection name 'invalid collection name'"
    ):
        collection_service.create_collection(
            "invalid collection name", enable_hybrid=False
        )


def test_load_collection_invalid_path(collection_service, test_collection):
    """Test that load_collection raises FileNotFoundError for invalid path."""
    with pytest.raises(FileNotFoundError, match="Path does not exist: invalid path"):
        collection_service.load_collection(test_collection, "invalid path")


def test_load_collection_security_vulnerabilities(collection_service, test_collection):
    """Test that load_collection raises ValueError for path traversal attempts."""
    with pytest.raises(ValueError, match="Path contains invalid traversal"):
        collection_service.load_collection(
            test_collection, "../../../../../../../../../../etc/passwd"
        )
