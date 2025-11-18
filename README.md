# VDB Manager

A command-line tool for managing Architecture Decision Records (ADRs) in vector databases. This tool enables you to create collections, load ADR markdown files, chunk and embed them, and manage your vector database collections with support for hybrid search (semantic + keyword-based search).

The project uses a hexagonal architecture pattern that allows for easy extension to support different vector database backends. Currently, Qdrant is implemented, but the architecture makes it straightforward to add support for other vector databases.

For a detailed list of changes, see [CHANGELOG.md](CHANGELOG.md).

## Features

- **Collection Management**: Create, delete, clear, list, and inspect vector database collections
- **ADR Loading**: Recursively load ADR markdown files from directories, automatically chunk and embed them
- **Hybrid Search Support**: Create collections with hybrid search enabled (semantic + BM25 keyword search)
- **Embedding Generation**: Uses Ollama with the `nomic-embed-text` model for generating embeddings
- **Extensible Architecture**: Hexagonal architecture with database port/adapter pattern, making it easy to add support for different vector database backends
- **Current Backend**: Qdrant (with support for other backends via adapter pattern)

## Installation

### From Git Repository

Install directly from the GitHub repository:

```bash
pip install git+https://github.com/cloro7/vdb-manager.git
```

To install a specific branch or tag:

```bash
# Install from a specific branch
pip install git+https://github.com/cloro7/vdb-manager.git@branch-name

# Install from a specific tag
pip install git+https://github.com/cloro7/vdb-manager.git@v1.0.0
```


### From Source

Clone the repository and install in development mode:

```bash
git clone <repository-url>
cd vdb-manager
pip install -e .
```

### Install as Package

Build and install the package:

```bash
pip install build
python -m build
pip install dist/vdb-manager-*.whl
```

Or install directly from the source directory:

```bash
pip install .
```

### Development Setup

For development, install with dev dependencies and set up pre-commit hooks:

```bash
pip install -e ".[dev]"
pre-commit install
```

This will set up pre-commit hooks that run `black` and `flake8` automatically on every commit.

## Usage

### CLI

The CLI provides commands for managing your vector database collections and loading ADRs.

#### Create a Collection

Create a new collection with hybrid search enabled (default):

```bash
vdb-manager create my-adr-collection
```

Create a collection with a specific distance metric:

```bash
vdb-manager create my-adr-collection --distance Cosine
vdb-manager create my-adr-collection --distance Euclid
vdb-manager create my-adr-collection --distance Dot
```

Create a collection with semantic search only (disable hybrid search):

```bash
vdb-manager create my-adr-collection --distance Cosine --no-hybrid
```

Create a collection with a custom vector size:

```bash
vdb-manager create my-adr-collection --vector-size 1024
```

#### Check Version

Display the version of vdb-manager:

```bash
vdb-manager version
```

#### Load ADRs into a Collection

Load all markdown files from a directory (recursively) into a collection:

```bash
vdb-manager load my-adr-collection /path/to/adr/directory
```

The tool will:
- Recursively find all `.md` files in the specified directory
- Clean and chunk the text
- Generate embeddings using Ollama
- Upload chunks to the vector database collection

Example:

```bash
vdb-manager load my-adr-collection ~/projects/my-project/docs/adr
```

#### List Collections

List all collections in your vector database instance:

```bash
vdb-manager list
```

#### Get Collection Information

Get detailed information about a specific collection:

```bash
vdb-manager info my-adr-collection
```

#### Clear a Collection

Remove all vectors from a collection without deleting the collection itself:

```bash
vdb-manager clear my-adr-collection
```

#### Delete a Collection

Permanently delete a collection:

```bash
vdb-manager delete my-adr-collection
```

## Configuration

VDB Manager can be configured via a `config.yaml` file or environment variables. A complete example configuration file is available at `examples/config.example.yaml`.

### Configuration Precedence

Configuration values are loaded in the following order (later sources override earlier ones):

1. **Default values** - Hardcoded defaults in the application
2. **Config file** (`~/.vdb-manager/config.yaml` or `~/.vdb-manager/config.yml`) - Values from the configuration file override defaults
3. **Environment variables** - Environment variables override both defaults and config file values

This means:
- If a setting is not in your config file, the default value is used
- If a setting is in your config file, it overrides the default
- If an environment variable is set, it overrides both the default and config file value

**Example:**
```bash
# ~/.vdb-manager/config.yaml (or config.yml) has: db_requests_per_second: 100
# Environment has: DB_RATE_LIMIT=200
# Result: 200 (environment variable wins)
```

### Configuration File

The configuration file is located at `~/.vdb-manager/config.yaml` or `~/.vdb-manager/config.yml` (both are supported, with `config.yaml` taking precedence if both exist). Copy the example configuration file to this location:

```bash
mkdir -p ~/.vdb-manager
cp examples/config.example.yaml ~/.vdb-manager/config.yaml
# or
cp examples/config.example.yaml ~/.vdb-manager/config.yml
```

The `~/.vdb-manager/` directory will be created automatically if it doesn't exist when you first run VDB Manager. However, you'll need to create the `config.yaml` or `config.yml` file manually if you want to customize settings.

Then customize the settings as needed. The configuration file supports:

- **Database settings**: Database type and URL
- **Ollama settings**: API URL, model name, and timeout
- **Text processing**: Chunk size, overlap, and max text length
- **Rate limiting**: Database and embedding API request rate limits, with option to disable (development only)

### Environment Variables

You can override any configuration setting using environment variables:

- `VECTOR_DB_TYPE` - Database type (e.g., "qdrant")
- `QDRANT_URL` or `DATABASE_URL` - Database URL
- `OLLAMA_URL` - Ollama API endpoint
- `OLLAMA_MODEL` - Embedding model name
- `OLLAMA_TIMEOUT` - Request timeout in seconds
- `CHUNK_SIZE` - Text chunk size in words
- `CHUNK_OVERLAP` - Chunk overlap in words
- `RATE_LIMITING_DISABLED` - Set to "true", "1", or "yes" to disable rate limiting (development only)
- `DB_RATE_LIMIT` - Database requests per second
- `EMBEDDING_RATE_LIMIT` - Embedding API requests per second

Example:

```bash
export QDRANT_URL="http://localhost:6333"
export OLLAMA_URL="http://localhost:11434/api/embeddings"
export DB_RATE_LIMIT=200
vdb-manager create my-collection
```

## Security

VDB Manager implements multiple security measures to protect against common vulnerabilities and ensure safe operation.

### Input Validation

**Collection Name Validation**
- All collection names are validated using a strict regex pattern
- Prevents injection attacks by only allowing alphanumeric characters, hyphens, underscores, and dots
- Must start with alphanumeric character and be 1-63 characters long
- Applied to all operations: create, delete, clear, get info, upload, and search

**Distance Metric Validation**
- Only allows valid distance metrics: `Cosine`, `Euclid`, or `Dot`
- Prevents invalid configuration that could cause errors or unexpected behavior

**Path Validation**
- All file paths are validated and normalized before use
- Prevents directory traversal attacks (e.g., `../../../etc/passwd`)
- Blocks access to sensitive system directories (`/proc`, `/sys`)
- Validates path existence when required
- Expands user home directory (`~`) safely

### Rate Limiting

**Request Throttling**
- Database operations are rate-limited (default: 100 requests/second, configurable)
- Embedding API calls are rate-limited (default: 10 requests/second, configurable)
- Prevents abuse and protects against denial-of-service (DoS) attacks
- Thread-safe implementation ensures proper limiting in concurrent scenarios

### Network Security

**Request Timeouts**
- All network requests have configurable timeouts (default: 30 seconds for database, 60 seconds for embeddings)
- Prevents hanging requests that could exhaust resources
- Comprehensive error handling for timeouts, connection errors, and other network issues

**Error Handling**
- All network operations are wrapped in try-catch blocks
- Errors are logged with appropriate detail levels
- Network failures are handled gracefully without exposing sensitive information

### Data Integrity

**Hash Collision Handling**
- Uses SHA256 (instead of MD5) for generating deterministic UUIDs
- Implements collision detection and fallback UUID generation
- Verifies content matches before skipping uploads to prevent data corruption

**File Encoding Security**
- Handles Unicode encoding errors gracefully
- Uses UTF-8 with error replacement for files with encoding issues
- Prevents crashes from malformed file encodings
- Logs warnings when encoding issues are encountered

### Best Practices

- **No hardcoded secrets**: All sensitive values come from configuration or environment variables
- **Principle of least privilege**: Validation ensures only expected inputs are accepted
- **Defense in depth**: Multiple layers of validation and error handling
- **Secure defaults**: Sensible default values that prioritize security

### Security Recommendations

1. **Network Security**: Use HTTPS for database and embedding API connections in production
2. **Access Control**: Ensure proper network-level access controls for your Qdrant instance
3. **Environment Variables**: Store sensitive configuration (like API keys) in environment variables rather than config files
4. **Rate Limits**: Adjust rate limits based on your infrastructure capacity and requirements. **Never disable rate limiting in production** - it's a critical security feature that prevents abuse and DoS attacks
5. **File Permissions**: Ensure config files have appropriate file permissions (e.g., `chmod 600 ~/.vdb-manager/config.yaml` or `chmod 600 ~/.vdb-manager/config.yml`)

## Requirements

- Python 3.8+
- Vector database instance (currently Qdrant, default: `http://localhost:6333`)
- Ollama running with `nomic-embed-text` model (default: `http://localhost:11434`)

## Architecture

The project follows a hexagonal architecture pattern that enables extensibility:

- **Ports**: Abstract interfaces in `src/database/port.py` define the contract for vector database operations
- **Adapters**: Concrete implementations in `src/database/adapters/` (currently Qdrant in `qdrant.py`)
- **Services**: Business logic in `src/services/` that work with the abstract port interface
- **CLI**: Command-line interface in `src/cli/`

This architecture allows you to add support for other vector databases (e.g., Pinecone, Weaviate, Milvus) by implementing the `VectorDatabase` port interface in a new adapter, without modifying the core business logic or CLI.
