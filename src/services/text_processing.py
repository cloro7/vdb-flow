"""Text processing utilities."""
import re
from typing import List

CHUNK_SIZE = 800  # words per chunk (adjust if needed)
OVERLAP = 100     # overlap words between chunks for context continuity


def clean_text(text: str) -> str:
    """Basic cleanup for markdown and whitespace."""
    text = re.sub(r"#+\s*", "", text)  # remove markdown headers
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> List[str]:
    """
    Split text into overlapping word chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in words
        overlap: Number of overlapping words between chunks
        
    Returns:
        List of text chunks
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

