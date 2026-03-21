"""Unit tests for HttpOllamaCompatEmbedding (mocked HTTP)."""

import pytest
from unittest.mock import Mock, patch

import requests

from vdb_flow.embeddings.adapters.http_ollama_compat import HttpOllamaCompatEmbedding
from vdb_flow.embeddings.port import EmbeddingError


@pytest.fixture
def config():
    c = Mock()
    c.max_text_length = 100
    c.embedding_url = "http://ollama:11434/api/embeddings"
    c.embedding_model = "nomic-embed-text"
    c.embedding_timeout = 30
    return c


class TestHttpOllamaCompatEmbedding:
    def test_success_200(self, config):
        emb = HttpOllamaCompatEmbedding(config)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        with (
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.embedding_rate_limiter"
            ) as lim,
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.requests.post",
                return_value=mock_resp,
            ) as post,
        ):
            out = emb.embed("hello")
        lim.acquire.assert_called()
        post.assert_called_once()
        assert out == [0.1, 0.2, 0.3]
        call_kw = post.call_args.kwargs
        assert call_kw["json"] == {
            "model": "nomic-embed-text",
            "prompt": "hello",
        }

    def test_truncates_to_max_text_length(self, config):
        config.max_text_length = 4
        emb = HttpOllamaCompatEmbedding(config)
        mock_resp = Mock(status_code=200)
        mock_resp.json.return_value = {"embedding": [1.0]}
        with (
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.embedding_rate_limiter"
            ),
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.requests.post",
                return_value=mock_resp,
            ) as post,
        ):
            emb.embed("abcdefgh")
        assert post.call_args.kwargs["json"]["prompt"] == "abcd"

    def test_retries_then_success(self, config):
        emb = HttpOllamaCompatEmbedding(config)
        bad = Mock(status_code=503)
        good = Mock(status_code=200)
        good.json.return_value = {"embedding": [1.0, 0.0]}
        with (
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.embedding_rate_limiter"
            ),
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.requests.post",
                side_effect=[bad, good],
            ),
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.time.sleep"
            ) as sleep,
        ):
            out = emb.embed("x")
        assert out == [1.0, 0.0]
        assert sleep.called

    def test_raises_after_exhausted_non_200(self, config):
        emb = HttpOllamaCompatEmbedding(config)
        mock_resp = Mock(status_code=500)
        with (
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.embedding_rate_limiter"
            ),
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.requests.post",
                return_value=mock_resp,
            ),
            patch("vdb_flow.embeddings.adapters.http_ollama_compat.time.sleep"),
        ):
            with pytest.raises(EmbeddingError, match="Failed to get embedding"):
                emb.embed("x")

    def test_timeout_then_raises(self, config):
        emb = HttpOllamaCompatEmbedding(config)
        with (
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.embedding_rate_limiter"
            ),
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.requests.post",
                side_effect=requests.exceptions.Timeout("t"),
            ),
            patch("vdb_flow.embeddings.adapters.http_ollama_compat.time.sleep"),
        ):
            with pytest.raises(EmbeddingError):
                emb.embed("x")

    def test_connection_error_then_raises(self, config):
        emb = HttpOllamaCompatEmbedding(config)
        with (
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.embedding_rate_limiter"
            ),
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.requests.post",
                side_effect=requests.exceptions.ConnectionError("c"),
            ),
            patch("vdb_flow.embeddings.adapters.http_ollama_compat.time.sleep"),
        ):
            with pytest.raises(EmbeddingError):
                emb.embed("x")

    def test_generic_request_exception(self, config):
        emb = HttpOllamaCompatEmbedding(config)
        with (
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.embedding_rate_limiter"
            ),
            patch(
                "vdb_flow.embeddings.adapters.http_ollama_compat.requests.post",
                side_effect=requests.exceptions.RequestException("bad"),
            ),
            patch("vdb_flow.embeddings.adapters.http_ollama_compat.time.sleep"),
        ):
            with pytest.raises(EmbeddingError):
                emb.embed("x")
