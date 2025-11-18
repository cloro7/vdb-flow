"""Text processing utilities."""

import re
from typing import List, Optional

from ..config import get_config


def clean_text(text: str) -> str:
    """Clean markdown and whitespace from text."""
    text = re.sub(r"#+\s*", "", text)  # remove markdown headers
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_text(
    text: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None
) -> List[str]:
    """
    Split text into overlapping word chunks.

    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in words (defaults to config value)
        overlap: Number of overlapping words between chunks (defaults to config value)

    Returns:
        List of text chunks
    """
    config = get_config()
    if chunk_size is None:
        chunk_size = config.chunk_size
    if overlap is None:
        overlap = config.chunk_overlap

    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks
