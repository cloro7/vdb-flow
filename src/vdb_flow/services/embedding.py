"""Embedding service for generating text embeddings."""

import logging
import time
import requests
from typing import List

from ..config import get_config
from ..rate_limiter import embedding_rate_limiter

logger = logging.getLogger(__name__)


def get_embedding(text: str) -> List[float]:
    """
    Get embedding from Ollama with retries and size limits.

    Args:
        text: Text to embed

    Returns:
        Embedding vector

    Raises:
        RuntimeError: If embedding generation fails after retries
    """
    config = get_config()
    max_length = config.max_text_length
    text = text[:max_length]  # truncate overly long chunks

    ollama_url = config.ollama_url
    model = config.ollama_model
    timeout = config.ollama_timeout

    max_attempts = 3
    base_delay = 1  # Base delay in seconds for exponential backoff

    for attempt in range(1, max_attempts + 1):
        try:
            # Apply rate limiting before making request
            embedding_rate_limiter.acquire()

            resp = requests.post(
                ollama_url, json={"model": model, "prompt": text}, timeout=timeout
            )
            if resp.status_code == 200:
                if attempt > 1:
                    logger.info(f"Successfully got embedding on attempt {attempt}")
                return resp.json()["embedding"]
            else:
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed: "
                    f"Ollama returned {resp.status_code}"
                )
        except requests.exceptions.Timeout as e:
            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: "
                f"Ollama connection timeout: {e}"
            )
        except requests.exceptions.ConnectionError as e:
            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: "
                f"Unable to connect to Ollama at {ollama_url}: {e}"
            )
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: "
                f"Ollama request error: {e}"
            )

        # Apply exponential backoff before retrying (except on last attempt)
        if attempt < max_attempts:
            delay = base_delay * (
                2 ** (attempt - 1)
            )  # Exponential backoff: 1s, 2s, 4s, ...
            logger.debug(f"Waiting {delay}s before retry...")
            time.sleep(delay)

    raise RuntimeError(
        f"Failed to get embedding after {max_attempts} attempts. "
        f"Unable to connect to Ollama at {ollama_url}. "
        f"Please check that Ollama is running and accessible."
    )
