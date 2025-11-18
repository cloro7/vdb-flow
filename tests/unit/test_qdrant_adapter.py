"""Unit tests for QdrantVectorDatabase using mocks."""

import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout, ConnectionError, RequestException

from src.database.adapters.qdrant import (
    QdrantVectorDatabase,
    QdrantCollectionNotFoundError,
)
from src.database.port import (
    DatabaseConnectionError,
    DatabaseTimeoutError,
    DatabaseOperationError,
    InvalidCollectionNameError,
)


@pytest.fixture
def qdrant_url():
    """Return default Qdrant URL for testing."""
    return "http://localhost:6333"


@pytest.fixture
def qdrant_client(qdrant_url):
    """Create a QdrantVectorDatabase instance with mocked config."""
    # Patch get_config before creating the client
    with patch("src.config.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.qdrant_url = qdrant_url
        mock_get_config.return_value = mock_config

        client = QdrantVectorDatabase(qdrant_url=qdrant_url)
        yield client


class TestQdrantVectorDatabaseInit:
    """Test QdrantVectorDatabase initialization."""

    def test_init_with_url(self, qdrant_url):
        """Test initialization with explicit URL."""
        client = QdrantVectorDatabase(qdrant_url=qdrant_url)
        assert client.qdrant_url == qdrant_url

    def test_init_without_url(self):
        """Test initialization without URL (uses config)."""
        with patch("src.config.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.qdrant_url = "http://custom:6333"
            mock_get_config.return_value = mock_config

            client = QdrantVectorDatabase()
            assert client.qdrant_url == "http://custom:6333"

    def test_init_strips_trailing_slash(self, qdrant_url):
        """Test that trailing slash is stripped from URL."""
        client = QdrantVectorDatabase(qdrant_url=f"{qdrant_url}/")
        assert client.qdrant_url == qdrant_url


class TestQdrantVectorDatabaseMakeRequest:
    """Test QdrantVectorDatabase._make_request method."""

    def test_make_request_success(self, qdrant_client):
        """Test successful request."""
        with patch("src.database.adapters.qdrant.requests.get") as mock_get, patch(
            "src.database.adapters.qdrant.db_rate_limiter"
        ) as mock_limiter:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            resp, success = qdrant_client._make_request("get", "http://test.com")

            assert success is True
            assert resp.status_code == 200
            mock_limiter.acquire.assert_called_once()

    def test_make_request_with_json(self, qdrant_client):
        """Test request with JSON payload."""
        with patch("src.database.adapters.qdrant.requests.post") as mock_post, patch(
            "src.database.adapters.qdrant.db_rate_limiter"
        ):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            resp, success = qdrant_client._make_request(
                "post", "http://test.com", json={"key": "value"}
            )

            assert success is True
            mock_post.assert_called_once_with(
                "http://test.com", json={"key": "value"}, timeout=30
            )

    def test_make_request_timeout(self, qdrant_client):
        """Test request timeout handling."""
        with patch("src.database.adapters.qdrant.requests.get") as mock_get, patch(
            "src.database.adapters.qdrant.db_rate_limiter"
        ):
            mock_get.side_effect = Timeout("Connection timeout")

            with pytest.raises(DatabaseTimeoutError) as exc_info:
                qdrant_client._make_request("get", "http://test.com")

            assert "timeout" in str(exc_info.value).lower()
            assert "Qdrant" in str(exc_info.value)

    def test_make_request_connection_error(self, qdrant_client):
        """Test connection error handling."""
        with patch("src.database.adapters.qdrant.requests.get") as mock_get, patch(
            "src.database.adapters.qdrant.db_rate_limiter"
        ):
            mock_get.side_effect = ConnectionError("Connection failed")

            with pytest.raises(DatabaseConnectionError) as exc_info:
                qdrant_client._make_request("get", "http://test.com")

            assert "connection" in str(exc_info.value).lower()
            assert "Qdrant" in str(exc_info.value)

    def test_make_request_generic_error(self, qdrant_client):
        """Test generic request error handling."""
        with patch("src.database.adapters.qdrant.requests.get") as mock_get, patch(
            "src.database.adapters.qdrant.db_rate_limiter"
        ):
            mock_get.side_effect = RequestException("Request failed")

            with pytest.raises(DatabaseOperationError) as exc_info:
                qdrant_client._make_request("get", "http://test.com")

            assert "Qdrant" in str(exc_info.value)


class TestQdrantVectorDatabaseCollectionExists:
    """Test QdrantVectorDatabase._collection_exists method."""

    def test_collection_exists_true(self, qdrant_client):
        """Test that existing collection returns True."""
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_request.return_value = (mock_response, True)

            result = qdrant_client._collection_exists("test-collection")

            assert result is True
            mock_request.assert_called_once()

    def test_collection_exists_false(self, qdrant_client):
        """Test that non-existent collection returns False."""
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_request.return_value = (mock_response, True)

            result = qdrant_client._collection_exists("test-collection")

            assert result is False


class TestQdrantVectorDatabaseCreateCollection:
    """Test QdrantVectorDatabase.create_collection method."""

    def test_create_collection_success(self, qdrant_client):
        """Test successful collection creation."""
        with patch.object(
            qdrant_client, "_collection_exists"
        ) as mock_exists, patch.object(qdrant_client, "_make_request") as mock_request:
            mock_exists.return_value = False
            mock_response = Mock()
            mock_response.status_code = 200
            mock_request.return_value = (mock_response, True)

            qdrant_client.create_collection("test-collection", enable_hybrid=False)

            mock_exists.assert_called_once_with("test-collection")
            assert mock_request.called

    def test_create_collection_already_exists(self, qdrant_client):
        """Test creating collection that already exists."""
        with patch.object(
            qdrant_client, "_collection_exists"
        ) as mock_exists, patch.object(
            qdrant_client, "get_collection_info"
        ) as mock_get_info:
            mock_exists.return_value = True
            mock_get_info.return_value = {"status": "ok", "result": {}}

            # Should return existing collection info, not raise error
            result = qdrant_client.create_collection(
                "test-collection", enable_hybrid=False
            )

            assert result is not None
            mock_get_info.assert_called_once()

    def test_create_collection_hybrid(self, qdrant_client):
        """Test creating hybrid collection."""
        with patch.object(
            qdrant_client, "_collection_exists"
        ) as mock_exists, patch.object(qdrant_client, "_make_request") as mock_request:
            mock_exists.return_value = False
            mock_response = Mock()
            mock_response.status_code = 200
            mock_request.return_value = (mock_response, True)

            qdrant_client.create_collection("test-collection", enable_hybrid=True)

            # Verify request was made (check that payload includes sparse vectors)
            assert mock_request.called

    def test_create_collection_invalid_name(self, qdrant_client):
        """Test creating collection with invalid name."""
        # validate_collection_name raises ValueError, which is caught and re-raised as InvalidCollectionNameError
        with pytest.raises(InvalidCollectionNameError, match="Invalid collection name"):
            qdrant_client.create_collection(
                "invalid collection name", enable_hybrid=False
            )

    def test_create_collection_invalid_vector_size(self, qdrant_client):
        """Test creating collection with invalid vector size."""
        # QdrantVectorDatabase doesn't validate vector_size, it just passes it to Qdrant
        # The validation happens in CollectionService. So this test should expect
        # DatabaseOperationError from Qdrant, not InvalidVectorSizeError
        with patch.object(
            qdrant_client, "_collection_exists"
        ) as mock_exists, patch.object(qdrant_client, "_make_request") as mock_request:
            mock_exists.return_value = False
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = '{"error": "invalid vector size"}'
            mock_request.return_value = (mock_response, True)

            with pytest.raises(DatabaseOperationError):
                qdrant_client.create_collection(
                    "test-collection", vector_size=0, enable_hybrid=False
                )


class TestQdrantVectorDatabaseDeleteCollection:
    """Test QdrantVectorDatabase.delete_collection method."""

    def test_delete_collection_success(self, qdrant_client):
        """Test successful collection deletion."""
        with patch.object(
            qdrant_client, "_collection_exists"
        ) as mock_exists, patch.object(qdrant_client, "_make_request") as mock_request:
            mock_exists.return_value = True
            mock_response = Mock()
            mock_response.status_code = 200
            mock_request.return_value = (mock_response, True)

            qdrant_client.delete_collection("test-collection")

            mock_exists.assert_called_once_with("test-collection")
            assert mock_request.called

    def test_delete_collection_not_found(self, qdrant_client):
        """Test deleting non-existent collection."""
        # Mock both _collection_exists and _make_request
        with patch.object(
            qdrant_client, "_collection_exists"
        ) as mock_exists, patch.object(
            qdrant_client, "_make_request"
        ) as mock_request, patch(
            "src.database.adapters.qdrant.db_rate_limiter"
        ):
            mock_exists.return_value = False
            # Simulate successful DELETE response (Qdrant returns 200 even for non-existent)
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_request.return_value = (mock_resp, True)

            with pytest.raises(QdrantCollectionNotFoundError):
                qdrant_client.delete_collection("non-existent")

            # Verify that _make_request was called (even though collection doesn't exist)
            mock_request.assert_called_once()


class TestQdrantVectorDatabaseClearCollection:
    """Test QdrantVectorDatabase.clear_collection method."""

    def test_clear_collection_success(self, qdrant_client):
        """Test successful collection clearing."""
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_request.return_value = (mock_response, True)

            qdrant_client.clear_collection("test-collection")

            assert mock_request.called

    def test_clear_collection_not_found(self, qdrant_client):
        """Test clearing non-existent collection."""
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_request.return_value = (mock_response, True)

            with pytest.raises(QdrantCollectionNotFoundError):
                qdrant_client.clear_collection("non-existent")


class TestQdrantVectorDatabaseGetCollectionInfo:
    """Test QdrantVectorDatabase.get_collection_info method."""

    def test_get_collection_info_success(self, qdrant_client):
        """Test successful collection info retrieval."""
        expected_info = {"status": "ok", "result": {"points_count": 10}}
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_info
            mock_request.return_value = (mock_response, True)

            result = qdrant_client.get_collection_info("test-collection")

            assert result == expected_info

    def test_get_collection_info_not_found(self, qdrant_client):
        """Test getting info for non-existent collection."""
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_request.return_value = (mock_response, True)

            with pytest.raises(QdrantCollectionNotFoundError):
                qdrant_client.get_collection_info("non-existent")


class TestQdrantVectorDatabaseListCollections:
    """Test QdrantVectorDatabase.list_collections method."""

    def test_list_collections_success(self, qdrant_client):
        """Test successful collection listing."""
        expected_collections = [{"name": "collection1"}, {"name": "collection2"}]
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "result": {"collections": expected_collections}
            }
            mock_request.return_value = (mock_response, True)

            result = qdrant_client.list_collections()

            assert result == expected_collections

    def test_list_collections_empty(self, qdrant_client):
        """Test listing when no collections exist."""
        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"collections": []}}
            mock_request.return_value = (mock_response, True)

            result = qdrant_client.list_collections()

            assert result == []


class TestQdrantVectorDatabaseUploadChunk:
    """Test QdrantVectorDatabase.upload_chunk method."""

    def test_upload_chunk_success(self, qdrant_client):
        """Test successful chunk upload."""
        mock_embedding_func = Mock(return_value=[0.1] * 768)

        with patch.object(
            qdrant_client, "_check_point_exists"
        ) as mock_check_exists, patch.object(
            qdrant_client, "_ensure_hybrid_collection_cached"
        ) as mock_hybrid, patch.object(
            qdrant_client, "_make_request"
        ) as mock_request:
            # Point doesn't exist
            mock_check_exists.return_value = (False, False)
            mock_hybrid.return_value = False
            # Upload request succeeds
            mock_upload = Mock()
            mock_upload.status_code = 200
            mock_upload.ok = True
            mock_request.return_value = (mock_upload, True)

            qdrant_client.upload_chunk(
                "test-collection",
                "chunk text",
                "test.md",
                0,
                mock_embedding_func,
            )

            assert mock_request.called
            mock_embedding_func.assert_called_once_with("chunk text")

    def test_upload_chunk_hash_collision(self, qdrant_client):
        """Test handling of hash collision."""
        mock_embedding_func = Mock(return_value=[0.1] * 768)

        with patch.object(qdrant_client, "_make_request") as mock_request:
            # First call: point exists with different content
            mock_existing = Mock()
            mock_existing.status_code = 200
            mock_existing.json.return_value = {
                "result": {"payload": {"chunk_text": "different content"}}
            }

            # Second call: successful upload with fallback UUID
            mock_success = Mock()
            mock_success.status_code = 200

            mock_request.side_effect = [
                (mock_existing, True),  # Check existing point
                (mock_success, True),  # Upload with fallback UUID
            ]

            qdrant_client.upload_chunk(
                "test-collection",
                "chunk text",
                "test.md",
                0,
                mock_embedding_func,
            )

            # Should have made multiple requests (check + upload with fallback)
            assert mock_request.call_count >= 2


class TestQdrantVectorDatabaseUploadChunksBatch:
    """Test QdrantVectorDatabase.upload_chunks_batch method."""

    def test_upload_chunks_batch_success(self, qdrant_client):
        """Test successful batch upload."""
        mock_embedding_func = Mock(side_effect=[[0.1] * 768, [0.2] * 768])
        chunks = [
            ("chunk 1", "file1.md", 0),
            ("chunk 2", "file1.md", 1),
        ]

        # With 2 chunks, it will use parallel processing (max_workers > 1 and len(chunks) > 1)
        # So we need to mock _prepare_points_parallel instead
        with patch.object(
            qdrant_client, "_ensure_hybrid_collection_cached"
        ) as mock_hybrid, patch.object(
            qdrant_client, "_prepare_points_parallel"
        ) as mock_prepare_parallel, patch.object(
            qdrant_client, "_prepare_points_sequential"
        ) as mock_prepare_sequential, patch.object(
            qdrant_client, "_upload_batch_points"
        ) as mock_upload:
            mock_hybrid.return_value = False

            # Mock the parallel prepare to call the embedding function
            def prepare_side_effect(
                chunks, embedding_func, is_hybrid, max_workers, progress_callback
            ):
                # Call embedding function for each chunk to verify it's used
                for chunk_text, _, _ in chunks:
                    embedding_func(chunk_text)
                return [
                    {"id": "1", "vector": [0.1] * 768, "payload": {}},
                    {"id": "2", "vector": [0.2] * 768, "payload": {}},
                ]

            mock_prepare_parallel.side_effect = prepare_side_effect

            qdrant_client.upload_chunks_batch(
                "test-collection", chunks, mock_embedding_func
            )

            # Should use parallel processing for 2 chunks
            assert mock_prepare_parallel.called
            assert not mock_prepare_sequential.called
            assert mock_upload.called
            # Embedding function is called inside _prepare_points_parallel
            assert mock_embedding_func.call_count == 2

    def test_upload_chunks_batch_with_progress(self, qdrant_client):
        """Test batch upload with progress callback."""
        mock_embedding_func = Mock(side_effect=[[0.1] * 768, [0.2] * 768])
        chunks = [
            ("chunk 1", "file1.md", 0),
            ("chunk 2", "file1.md", 1),
        ]

        progress_callback = Mock()

        # With 2 chunks, it will use parallel processing
        with patch.object(
            qdrant_client, "_ensure_hybrid_collection_cached"
        ) as mock_hybrid, patch.object(
            qdrant_client, "_prepare_points_parallel"
        ) as mock_prepare_parallel, patch.object(
            qdrant_client, "_prepare_points_sequential"
        ) as mock_prepare_sequential, patch.object(
            qdrant_client, "_upload_batch_points"
        ):
            mock_hybrid.return_value = False

            # Mock the parallel prepare to call the progress callback
            def prepare_side_effect(
                chunks, embedding_func, is_hybrid, max_workers, progress_callback
            ):
                # Call embedding function for each chunk
                for chunk_text, _, _ in chunks:
                    embedding_func(chunk_text)
                # Call progress callback
                if progress_callback:
                    progress_callback(len(chunks))
                return [
                    {"id": "1", "vector": [0.1] * 768, "payload": {}},
                    {"id": "2", "vector": [0.2] * 768, "payload": {}},
                ]

            mock_prepare_parallel.side_effect = prepare_side_effect

            qdrant_client.upload_chunks_batch(
                "test-collection",
                chunks,
                mock_embedding_func,
                progress_callback=progress_callback,
            )

            # Verify parallel processing was used, not sequential
            assert mock_prepare_parallel.called
            assert not mock_prepare_sequential.called

            # Progress callback should be called during point preparation
            assert progress_callback.called


class TestQdrantVectorDatabaseSearch:
    """Test QdrantVectorDatabase.search method."""

    def test_search_success(self, qdrant_client):
        """Test successful search."""
        query_vector = [0.1] * 768
        expected_results = [
            {"id": "1", "score": 0.95, "payload": {"chunk_text": "result 1"}},
            {"id": "2", "score": 0.85, "payload": {"chunk_text": "result 2"}},
        ]

        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": expected_results}
            mock_request.return_value = (mock_response, True)

            results = qdrant_client.search("test-collection", query_vector, limit=5)

            assert len(results) == 2
            assert results[0]["score"] == 0.95

    def test_search_invalid_collection(self, qdrant_client):
        """Test search with invalid collection name."""
        with pytest.raises(InvalidCollectionNameError):
            qdrant_client.search("invalid collection", [0.1] * 768, limit=5)

    def test_search_not_found(self, qdrant_client):
        """Test search on non-existent collection."""
        query_vector = [0.1] * 768

        with patch.object(qdrant_client, "_make_request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_request.return_value = (mock_response, True)

            with pytest.raises(QdrantCollectionNotFoundError):
                qdrant_client.search("non-existent", query_vector, limit=5)
