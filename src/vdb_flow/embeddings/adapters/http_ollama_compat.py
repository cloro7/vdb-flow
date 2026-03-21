"""HTTP adapter: Ollama-compatible embeddings API (POST model + prompt -> embedding)."""

import logging
import time
from typing import List

import requests

from ...config import Config
from ...rate_limiter import embedding_rate_limiter
from .. import register_embedding_adapter
from ..port import EmbeddingProvider, EmbeddingError

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY = 1.0


class HttpOllamaCompatEmbedding(EmbeddingProvider):
    r"""Calls an HTTP endpoint that accepts Ollama-style JSON and returns ``{"embedding": [...]}``."""

    def __init__(self, config: Config):
        """Store config for URL, model, timeout, and truncation."""
        self._config = config

    def embed(self, text: str) -> List[float]:
        """
        Embed a single text chunk via Ollama-style HTTP POST.

        Args:
            text: Input text (truncated per ``max_text_length``)

        Returns:
            Embedding vector from the JSON ``embedding`` field.

        Raises:
            EmbeddingError: If the HTTP API fails after retries.
        """
        max_length = self._config.max_text_length
        text = text[:max_length]
        url = self._config.embedding_url
        model = self._config.embedding_model
        timeout = self._config.embedding_timeout

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                embedding_rate_limiter.acquire()
                resp = requests.post(
                    url,
                    json={"model": model, "prompt": text},
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    if attempt > 1:
                        logger.info(f"Successfully got embedding on attempt {attempt}")
                    return resp.json()["embedding"]
                logger.warning(
                    f"Attempt {attempt}/{_MAX_ATTEMPTS} failed: "
                    f"embedding API returned {resp.status_code}"
                )
            except requests.exceptions.Timeout as e:
                logger.warning(
                    f"Attempt {attempt}/{_MAX_ATTEMPTS} failed: "
                    f"embedding API timeout: {e}"
                )
            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    f"Attempt {attempt}/{_MAX_ATTEMPTS} failed: "
                    f"unable to connect to embedding API at {url}: {e}"
                )
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Attempt {attempt}/{_MAX_ATTEMPTS} failed: "
                    f"embedding request error: {e}"
                )

            if attempt < _MAX_ATTEMPTS:
                delay = _BASE_DELAY * (2 ** (attempt - 1))
                logger.debug(f"Waiting {delay}s before retry...")
                time.sleep(delay)

        raise EmbeddingError(
            f"Failed to get embedding after {_MAX_ATTEMPTS} attempts. "
            f"Unable to reach the embedding HTTP API at {url}. "
            f"Check that the service is running and EMBEDDING_URL / config embeddings.url is correct."
        )


def _register() -> None:
    register_embedding_adapter(
        "http_ollama_compat", lambda config: HttpOllamaCompatEmbedding(config)
    )


_register()
