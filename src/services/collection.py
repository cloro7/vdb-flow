"""Collection service for loading and managing ADR collections."""
import os
import logging
from pathlib import Path
from typing import Protocol

from ..database.port import VectorDatabase
from .text_processing import clean_text, chunk_text
from .embedding import get_embedding

logger = logging.getLogger(__name__)


class CollectionService:
    """Service for managing ADR collections."""
    
    def __init__(self, db_client: VectorDatabase):
        """
        Initialize collection service.
        
        Args:
            db_client: Vector database client implementing VectorDatabase port
        """
        self.db_client = db_client
    
    def load_collection(self, collection_name: str, path: str) -> None:
        """
        Recursively read all .md ADRs from path, chunk them, and upload.
        
        Args:
            collection_name: Name of the collection
            path: Path to ADR directory (can include subfolders)
        """
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = clean_text(f.read())
                    chunks = chunk_text(text)
                    rel_path = os.path.relpath(file_path, path)
                    logger.info(f"Uploading {rel_path}: {len(chunks)} chunks to {collection_name}")
                    for i, chunk in enumerate(chunks):
                        self.db_client.upload_chunk(
                            collection_name, 
                            chunk, 
                            rel_path, 
                            i + 1, 
                            get_embedding
                        )

