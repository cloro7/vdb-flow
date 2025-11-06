import os
import re
import time
import logging
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database import QdrantVectorDatabase

# Set up logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text:latest"

CHUNK_SIZE = 800  # words per chunk (adjust if needed)
OVERLAP = 100     # overlap words between chunks for context continuity

# Initialize database client
_db_client = QdrantVectorDatabase()


def clean_text(text):
    """Basic cleanup for markdown and whitespace."""
    text = re.sub(r"#+\s*", "", text)  # remove markdown headers
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """Split text into overlapping word chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


def get_embedding(text):
    """Get embedding from Ollama with retries and size limits."""
    import requests
    
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


def load_collection(collection_name, path):
    """Recursively read all .md ADRs from path, chunk them, and upload."""
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
                    _db_client.upload_chunk(collection_name, chunk, rel_path, i + 1, get_embedding)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage ADR embeddings in Qdrant.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Load command
    load_parser = subparsers.add_parser("load", help="Load ADRs into a Qdrant collection.")
    load_parser.add_argument("collection", help="Name of the collection to create or update.")
    load_parser.add_argument("path", help="Path to ADR directory (can include subfolders).")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an existing collection.")
    delete_parser.add_argument("collection", help="Name of the collection to delete.")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Remove all vectors from a collection without deleting it.")
    clear_parser.add_argument("collection", help="Name of the collection to clear.")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new collection.")
    create_parser.add_argument("collection", help="Name of the collection to create.")
    create_parser.add_argument("distance", nargs='?', default="Cosine", help="Distance metric to use (Cosine, Euclid, Dot).")

    # List command
    list_parser = subparsers.add_parser("list", help="List all collections.")

    # Get collection info command
    get_info_parser = subparsers.add_parser("info", help="Get information about a collection.")
    get_info_parser.add_argument("collection", help="Name of the collection to get information about.")

    args = parser.parse_args()

    if args.action == "delete":
        _db_client.delete_collection(args.collection)
        logger.info(f"Deleted collection: {args.collection}")
    elif args.action == "clear":
        _db_client.clear_collection(args.collection)
    elif args.action == "create":
        created_collection = _db_client.create_collection(args.collection, args.distance)
        logger.info(f"Created collection: {created_collection}")
    elif args.action == "list":
        collections = _db_client.list_collections()
        logger.info(f"Listed collections: {collections}")
    elif args.action == "info":
        collection_info = _db_client.get_collection_info(args.collection)
        logger.info(f"Collection info: {collection_info}")
    elif args.action == "load":
        adr_path = os.path.expanduser(args.path)
        if not os.path.exists(adr_path):
            logger.error(f"Path not found: {adr_path}")
            sys.exit(1)
        start_time = time.time()
        logger.info(f"Loading ADRs from {adr_path} into collection '{args.collection}' ...")
        load_collection(args.collection, adr_path)
        elapsed = time.time() - start_time
        minutes, seconds = divmod(elapsed, 60)
        logger.info(f"Done! Total runtime: {int(minutes)}m {seconds:.1f}s")

