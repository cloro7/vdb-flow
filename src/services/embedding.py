"""Embedding service for generating text embeddings."""
import logging
import requests
from typing import List

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text:latest"


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
    text = text[:5000]  # truncate overly long chunks (~5 KB)
    for attempt in range(3):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "prompt": text},
                timeout=60
            )
            if resp.status_code == 200:
                return resp.json()["embedding"]
            else:
                logger.warning(f"Ollama returned {resp.status_code}, retrying...")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama connection error: {e}, retrying...")
    raise RuntimeError("Failed to get embedding after 3 retries.")

