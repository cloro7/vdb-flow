"""Unit tests for CollectionService using mocks."""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from typing import List

from src.services.collection import CollectionService
from src.database.port import (
    CollectionNotFoundError,
    InvalidCollectionNameError,
    InvalidVectorSizeError,
)


@pytest.fixture
def mock_db_client():
    """Create a mock database client."""
    return Mock()


@pytest.fixture
def mock_embedding_func():
    """Create a mock embedding function."""

    def embedding_func(text: str) -> List[float]:
        # Return a deterministic embedding based on text length
        return [0.1] * 768

    return embedding_func


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = Mock()
    config.vector_size = 768
    config.chunk_size = 200
    config.chunk_overlap = 50
    config.restricted_paths = []
    config.denied_patterns = []
    config.allowed_patterns = []
    return config


@pytest.fixture
def collection_service(mock_db_client, mock_embedding_func, mock_config):
    """Create a CollectionService instance with mocked dependencies."""
    return CollectionService(
        db_client=mock_db_client,
        embedding_func=mock_embedding_func,
        config=mock_config,
    )


class TestCollectionServiceCreateCollection:
    """Test CollectionService.create_collection method."""

    def test_create_collection_success(self, collection_service, mock_db_client):
        """Test successful collection creation."""
        collection_name = "test-collection"
        mock_db_client.create_collection.return_value = {"status": "ok"}

        collection_service.create_collection(collection_name, enable_hybrid=False)

        mock_db_client.create_collection.assert_called_once_with(
            collection_name,
            "Cosine",
            vector_size=768,
            enable_hybrid=False,
        )

    def test_create_collection_with_custom_vector_size(
        self, collection_service, mock_db_client
    ):
        """Test collection creation with custom vector size."""
        collection_name = "test-collection"
        mock_db_client.create_collection.return_value = {"status": "ok"}

        collection_service.create_collection(
            collection_name, vector_size=1024, enable_hybrid=False
        )

        mock_db_client.create_collection.assert_called_once_with(
            collection_name,
            "Cosine",
            vector_size=1024,
            enable_hybrid=False,
        )

    def test_create_collection_with_hybrid(self, collection_service, mock_db_client):
        """Test collection creation with hybrid search enabled."""
        collection_name = "test-collection"
        mock_db_client.create_collection.return_value = {"status": "ok"}

        collection_service.create_collection(collection_name, enable_hybrid=True)

        mock_db_client.create_collection.assert_called_once_with(
            collection_name,
            "Cosine",
            vector_size=768,
            enable_hybrid=True,
        )

    def test_create_collection_invalid_name(self, collection_service):
        """Test collection creation with invalid name."""
        with pytest.raises(InvalidCollectionNameError):
            collection_service.create_collection(
                "invalid collection name", enable_hybrid=False
            )

    def test_create_collection_invalid_vector_size_zero(self, collection_service):
        """Test collection creation with zero vector size."""
        with pytest.raises(InvalidVectorSizeError):
            collection_service.create_collection(
                "test-collection", vector_size=0, enable_hybrid=False
            )

    def test_create_collection_invalid_vector_size_negative(self, collection_service):
        """Test collection creation with negative vector size."""
        with pytest.raises(InvalidVectorSizeError):
            collection_service.create_collection(
                "test-collection", vector_size=-1, enable_hybrid=False
            )

    def test_create_collection_uses_config_vector_size(
        self, collection_service, mock_db_client, mock_config
    ):
        """Test that collection creation uses vector_size from config if not provided."""
        collection_name = "test-collection"
        mock_config.vector_size = 512
        mock_db_client.create_collection.return_value = {"status": "ok"}

        collection_service.create_collection(collection_name, enable_hybrid=False)

        mock_db_client.create_collection.assert_called_once_with(
            collection_name,
            "Cosine",
            vector_size=512,
            enable_hybrid=False,
        )


class TestCollectionServiceDeleteCollection:
    """Test CollectionService.delete_collection method."""

    def test_delete_collection_success(self, collection_service, mock_db_client):
        """Test successful collection deletion."""
        collection_name = "test-collection"
        mock_db_client.delete_collection.return_value = None

        collection_service.delete_collection(collection_name)

        mock_db_client.delete_collection.assert_called_once_with(collection_name)

    def test_delete_collection_not_found(self, collection_service, mock_db_client):
        """Test deletion of non-existent collection."""
        collection_name = "non-existent"
        mock_db_client.delete_collection.side_effect = CollectionNotFoundError(
            "Collection not found"
        )

        with pytest.raises(CollectionNotFoundError):
            collection_service.delete_collection(collection_name)

    def test_delete_collection_invalid_name(self, collection_service):
        """Test deletion with invalid collection name."""
        with pytest.raises(InvalidCollectionNameError):
            collection_service.delete_collection("invalid collection name")


class TestCollectionServiceClearCollection:
    """Test CollectionService.clear_collection method."""

    def test_clear_collection_success(self, collection_service, mock_db_client):
        """Test successful collection clearing."""
        collection_name = "test-collection"
        mock_db_client.clear_collection.return_value = None

        collection_service.clear_collection(collection_name)

        mock_db_client.clear_collection.assert_called_once_with(collection_name)

    def test_clear_collection_not_found(self, collection_service, mock_db_client):
        """Test clearing non-existent collection."""
        collection_name = "non-existent"
        mock_db_client.clear_collection.side_effect = CollectionNotFoundError(
            "Collection not found"
        )

        with pytest.raises(CollectionNotFoundError):
            collection_service.clear_collection(collection_name)


class TestCollectionServiceGetCollectionInfo:
    """Test CollectionService.get_collection_info method."""

    def test_get_collection_info_success(self, collection_service, mock_db_client):
        """Test successful collection info retrieval."""
        collection_name = "test-collection"
        expected_info = {"status": "ok", "result": {"points_count": 10}}
        mock_db_client.get_collection_info.return_value = expected_info

        result = collection_service.get_collection_info(collection_name)

        assert result == expected_info
        mock_db_client.get_collection_info.assert_called_once_with(collection_name)

    def test_get_collection_info_not_found(self, collection_service, mock_db_client):
        """Test getting info for non-existent collection."""
        collection_name = "non-existent"
        mock_db_client.get_collection_info.side_effect = CollectionNotFoundError(
            "Collection not found"
        )

        with pytest.raises(CollectionNotFoundError):
            collection_service.get_collection_info(collection_name)


class TestCollectionServiceListCollections:
    """Test CollectionService.list_collections method."""

    def test_list_collections_success(self, collection_service, mock_db_client):
        """Test successful collection listing."""
        # list_collections returns List[Dict[str, Any]], not List[str]
        expected_collections = [
            {"name": "collection1"},
            {"name": "collection2"},
            {"name": "collection3"},
        ]
        mock_db_client.list_collections.return_value = expected_collections

        result = collection_service.list_collections()

        assert result == expected_collections
        mock_db_client.list_collections.assert_called_once()


class TestCollectionServiceLoadCollection:
    """Test CollectionService.load_collection method."""

    @pytest.fixture
    def test_adr_dir(self):
        """Create a temporary directory with test ADR files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test ADR file
            adr_file = Path(tmpdir) / "adr-001-test.md"
            adr_file.write_text(
                """# ADR-001: Test Decision

## Status
Accepted

## Context
This is a test architecture decision record for unit testing.

## Decision
We will use this ADR for testing purposes.

## Consequences
- Positive: Allows us to test the collection service
- Negative: None, it's just a test
"""
            )
            yield tmpdir

    def test_load_collection_success(
        self, collection_service, mock_db_client, test_adr_dir
    ):
        """Test successful collection loading."""
        collection_name = "test-collection"
        # get_collection_info must return a dict with "result" key for validation to pass
        mock_db_client.get_collection_info.return_value = {
            "status": "ok",
            "result": {"points_count": 0},
        }
        mock_db_client.upload_chunks_batch.return_value = None

        collection_service.load_collection(collection_name, test_adr_dir)

        # Verify collection existence was checked
        mock_db_client.get_collection_info.assert_called_once_with(collection_name)

        # Verify upload was called (at least once, may be multiple batches)
        assert mock_db_client.upload_chunks_batch.called

    def test_load_collection_collection_not_found(
        self, collection_service, mock_db_client, test_adr_dir
    ):
        """Test loading into non-existent collection."""
        collection_name = "non-existent"
        mock_db_client.get_collection_info.side_effect = CollectionNotFoundError(
            "Collection not found"
        )

        # CollectionService raises ValueError, not CollectionNotFoundError
        with pytest.raises(ValueError, match="does not exist"):
            collection_service.load_collection(collection_name, test_adr_dir)

    def test_load_collection_no_md_files(self, collection_service, mock_db_client):
        """Test loading from directory with no .md files."""
        collection_name = "test-collection"
        mock_db_client.get_collection_info.return_value = {
            "status": "ok",
            "result": {"points_count": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a non-.md file
            (Path(tmpdir) / "test.txt").touch()

            collection_service.load_collection(collection_name, tmpdir)

            # Should not call upload since no .md files
            mock_db_client.upload_chunks_batch.assert_not_called()

    def test_load_collection_multiple_files(self, collection_service, mock_db_client):
        """Test loading multiple ADR files."""
        collection_name = "test-collection"
        mock_db_client.get_collection_info.return_value = {
            "status": "ok",
            "result": {"points_count": 0},
        }
        mock_db_client.upload_chunks_batch.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple ADR files
            for i in range(3):
                adr_file = Path(tmpdir) / f"adr-00{i+1}.md"
                adr_file.write_text(f"# ADR-00{i+1}\n\nTest content {i+1}")

            collection_service.load_collection(collection_name, tmpdir)

            # Verify upload was called
            assert mock_db_client.upload_chunks_batch.called

    def test_load_collection_uses_injected_embedding_func(
        self, mock_db_client, mock_config
    ):
        """Test that load_collection uses injected embedding function."""
        collection_name = "test-collection"
        mock_embedding = Mock(return_value=[0.5] * 768)
        mock_db_client.get_collection_info.return_value = {
            "status": "ok",
            "result": {"points_count": 0},
        }
        mock_db_client.upload_chunks_batch.return_value = None

        service = CollectionService(
            db_client=mock_db_client,
            embedding_func=mock_embedding,
            config=mock_config,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            adr_file = Path(tmpdir) / "test.md"
            adr_file.write_text("# Test\n\nContent")

            service.load_collection(collection_name, tmpdir)

            # Verify upload_chunks_batch was called
            assert mock_db_client.upload_chunks_batch.called

            # Get the embedding function that was passed to upload_chunks_batch
            call_args = mock_db_client.upload_chunks_batch.call_args
            embedding_func_passed = call_args[0][
                2
            ]  # Third positional argument (collection_name, batch, embedding_func, ...)

            # Verify the embedding function passed is the injected one
            # by calling it and checking it returns the expected value
            assert callable(embedding_func_passed)
            result = embedding_func_passed("test text")
            assert result == [0.5] * 768
            assert mock_embedding.called

    def test_load_collection_handles_upload_errors(
        self, collection_service, mock_db_client, test_adr_dir
    ):
        """Test that load_collection handles upload errors gracefully."""
        collection_name = "test-collection"
        mock_db_client.get_collection_info.return_value = {
            "status": "ok",
            "result": {"points_count": 0},
        }
        # First call succeeds, second fails
        mock_db_client.upload_chunks_batch.side_effect = [
            None,
            Exception("Upload failed"),
            None,
        ]

        # Should not raise, but log errors
        collection_service.load_collection(collection_name, test_adr_dir)

        # Verify multiple upload attempts were made
        assert mock_db_client.upload_chunks_batch.call_count >= 1

    def test_load_collection_path_validation(self, collection_service, mock_db_client):
        """Test that load_collection validates paths."""
        collection_name = "test-collection"
        mock_db_client.get_collection_info.return_value = {
            "status": "ok",
            "result": {"points_count": 0},
        }

        # Invalid path (doesn't exist)
        with pytest.raises(FileNotFoundError):
            collection_service.load_collection(collection_name, "/nonexistent/path")


class TestCollectionServiceHelperMethods:
    """Test CollectionService helper methods."""

    def test_get_embedding_uses_injected_func(self, mock_db_client, mock_config):
        """Test that _get_embedding uses injected embedding function."""
        mock_embedding = Mock(return_value=[0.5] * 768)
        service = CollectionService(
            db_client=mock_db_client,
            embedding_func=mock_embedding,
            config=mock_config,
        )

        result = service._get_embedding("test text")

        assert result == [0.5] * 768
        mock_embedding.assert_called_once_with("test text")

    def test_get_embedding_falls_back_to_default(self, mock_db_client, mock_config):
        """Test that _get_embedding falls back to default if no function injected."""
        service = CollectionService(
            db_client=mock_db_client,
            embedding_func=None,
            config=mock_config,
        )

        with patch("src.services.embedding.get_embedding") as mock_default:
            mock_default.return_value = [0.3] * 768
            result = service._get_embedding("test text")

            assert result == [0.3] * 768
            mock_default.assert_called_once_with("test text")

    def test_get_config_uses_injected_config(self, mock_db_client, mock_config):
        """Test that _get_config uses injected config."""
        service = CollectionService(
            db_client=mock_db_client,
            config=mock_config,
        )

        result = service._get_config()

        assert result is mock_config

    def test_get_config_falls_back_to_global(self, mock_db_client):
        """Test that _get_config falls back to global config if not injected."""
        service = CollectionService(db_client=mock_db_client, config=None)

        with patch("src.config.get_config") as mock_get_config:
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            result = service._get_config()

            assert result is mock_config
            mock_get_config.assert_called_once()

    def test_read_file_with_fallback_success(self, collection_service):
        """Test _read_file_with_fallback with valid file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Test content")

            result = CollectionService._read_file_with_fallback(
                str(test_file), "test.txt"
            )

            assert result == "Test content"

    def test_read_file_with_fallback_encoding_error(self, collection_service):
        """Test _read_file_with_fallback handles encoding errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.bin"
            # Write binary data that's not valid UTF-8
            test_file.write_bytes(b"\xff\xfe\x00\x01")

            # Should attempt fallback encoding
            result = CollectionService._read_file_with_fallback(
                str(test_file), "test.bin"
            )

            # Should return something (even if it's garbled)
            assert isinstance(result, str)
