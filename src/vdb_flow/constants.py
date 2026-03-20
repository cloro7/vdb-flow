"""Constants used throughout the VDB Manager application."""

# Vector database constants
DEFAULT_VECTOR_SIZE = 768  # Default size for embedding vectors

# Text processing constants
DEFAULT_CHUNK_SIZE = 800  # Default chunk size in words
DEFAULT_CHUNK_OVERLAP = 100  # Default overlap between chunks

# Batch processing constants
DEFAULT_BATCH_SIZE = 50  # Default number of chunks per batch upload
DEFAULT_MAX_WORKERS = 4  # Default number of parallel workers for embedding generation

# Rate limiting constants
DEFAULT_DB_RATE_LIMIT = 100  # Default database requests per second
DEFAULT_EMBEDDING_RATE_LIMIT = 10  # Default embedding requests per second
