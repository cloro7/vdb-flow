# VDB Flow

[![CI](https://github.com/cloro7/vdb-flow/actions/workflows/ci.yml/badge.svg)](https://github.com/cloro7/vdb-flow/actions/workflows/ci.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A command-line tool for managing Architecture Decision Records (ADRs) in vector databases. This tool enables you to create collections, load ADR markdown files, chunk and embed them, and manage your vector database collections with support for hybrid search (semantic + keyword-based search).

The project uses a hexagonal architecture pattern that allows for easy extension to support different vector database backends. Currently, Qdrant is implemented, but the architecture makes it straightforward to add support for other vector databases.

For a detailed list of changes, see [CHANGELOG.md](CHANGELOG.md).

## Features

- **Collection Management**: Create, delete, clear, list, and inspect vector database collections
- **ADR Loading**: Recursively load ADR markdown files from directories, automatically chunk and embed them
- **Hybrid Search Support**: Create collections with hybrid search enabled (semantic + BM25 keyword search)
- **Embedding Generation**: Uses Ollama with the `nomic-embed-text` model for generating embeddings
- **Extensible Architecture**: Hexagonal architecture with pluggable adapter registry, making it easy to add support for different vector database backends
- **Pluggable Adapters**: Adapter registry system allows third-party adapters to be registered without modifying core code
- **Current Backend**: Qdrant (with support for other backends via adapter pattern and entry points)

## Installation

### From Git Repository

Install directly from the GitHub repository:

```bash
pip install git+https://github.com/cloro7/vdb-flow.git
```

To install a specific branch or tag:

```bash
# Install from a specific branch
pip install git+https://github.com/cloro7/vdb-flow.git@branch-name

# Install from a specific tag
pip install git+https://github.com/cloro7/vdb-flow.git@v1.0.0
```


### From Source

Clone the repository and install in development mode:

```bash
git clone <repository-url>
cd vdb-flow
pip install -e .
```

### Install as Package

Build and install the package:

```bash
pip install build
python -m build
pip install dist/vdb-flow-*.whl
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
vdb-flow create my-adr-collection
```

Create a collection with a specific distance metric:

```bash
vdb-flow create my-adr-collection --distance Cosine
vdb-flow create my-adr-collection --distance Euclid
vdb-flow create my-adr-collection --distance Dot
```

Create a collection with semantic search only (disable hybrid search):

```bash
vdb-flow create my-adr-collection --distance Cosine --no-hybrid
```

Create a collection with a custom vector size:

```bash
vdb-flow create my-adr-collection --vector-size 1024
```

#### Check Version

Display the version of vdb-flow:

```bash
vdb-flow version
```

#### Load ADRs into a Collection

Load all markdown files from a directory (recursively) into a collection:

```bash
vdb-flow load my-adr-collection /path/to/adr/directory
```

The tool will:
- Recursively find all `.md` files in the specified directory
- Clean and chunk the text
- Generate embeddings using Ollama
- Upload chunks to the vector database collection

Example:

```bash
vdb-flow load my-adr-collection ~/projects/my-project/docs/adr
```

#### List Collections

List all collections in your vector database instance:

```bash
vdb-flow list
```

#### Get Collection Information

Get detailed information about a specific collection:

```bash
vdb-flow info my-adr-collection
```

#### Clear a Collection

Remove all vectors from a collection without deleting the collection itself:

```bash
vdb-flow clear my-adr-collection
```

#### Delete a Collection

Permanently delete a collection:

```bash
vdb-flow delete my-adr-collection
```

## Configuration

VDB Flow can be configured via a `config.yaml` file or environment variables. A complete example configuration file is available at `examples/config.example.yaml`.

### Configuration Precedence

Configuration values are loaded in the following order (later sources override earlier ones):

1. **Default values** - Hardcoded defaults in the application
2. **Config file** (`~/.vdb-flow/config.yaml` or `~/.vdb-flow/config.yml`) - Values from the configuration file override defaults
3. **Environment variables** - Environment variables override both defaults and config file values

This means:
- If a setting is not in your config file, the default value is used
- If a setting is in your config file, it overrides the default
- If an environment variable is set, it overrides both the default and config file value

**Example:**
```bash
# ~/.vdb-flow/config.yaml (or config.yml) has: db_requests_per_second: 100
# Environment has: DB_RATE_LIMIT=200
# Result: 200 (environment variable wins)
```

### Configuration File

The configuration file is located at `~/.vdb-flow/config.yaml` or `~/.vdb-flow/config.yml` (both are supported, with `config.yaml` taking precedence if both exist). Copy the example configuration file to this location:

```bash
mkdir -p ~/.vdb-flow
cp examples/config.example.yaml ~/.vdb-flow/config.yaml
# or
cp examples/config.example.yaml ~/.vdb-flow/config.yml
```

The `~/.vdb-flow/` directory will be created automatically if it doesn't exist when you first run VDB Flow. However, you'll need to create the `config.yaml` or `config.yml` file manually if you want to customize settings.

Then customize the settings as needed. The configuration file supports:

- **Database settings**: Database type and URL
- **Ollama settings**: API URL, model name, and timeout
- **Text processing**: Chunk size, overlap, and max text length
- **Rate limiting**: Database and embedding API request rate limits, with option to disable (development only)
- **Security settings**: Custom restricted paths to block access to specific directories

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
vdb-flow create my-collection
```

## Security

VDB Flow implements multiple security measures to protect against common vulnerabilities and ensure safe operation.

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
- **Always blocks** access to virtual filesystem directories (`/proc`, `/sys`, `/dev`, `/run`, `/var/run`) - these can leak kernel memory or device nodes
- **Optionally blocks** system directories (`/etc`, `/root`, `/boot`, `/sbin`, `/usr/sbin`) - these generate warnings by default but can be blocked via config
- **Custom restricted paths**: You can configure any custom directory path to block via `security.restricted_paths` in your config file
- **Glob pattern support**: Fine-grained control using `denied_patterns` and `allowed_patterns` with glob syntax
- Supports path normalization (expands `~`, resolves relative paths, handles `..` segments)
- Validates path existence when required
- Uses path boundary checks to prevent false positives (e.g., `/etcetera` is allowed even though it shares a prefix with `/etc`)
- **Audit logging**: Logs when denied patterns block access for security auditing

**Custom Restricted Paths Configuration**

You can add custom directories to block by configuring `security.restricted_paths` in your config file:

```yaml
security:
  restricted_paths:
    - /etc                    # System configuration directory
    - /root                   # Root user home directory
    - /mnt/secrets            # Custom restricted directory
    - ~/private               # User's private directory (expands to /home/user/private)
    - /var/sensitive          # Another custom restricted directory
```

**Important Security Requirement**: All paths in `restricted_paths` must be **absolute paths**. Relative paths are not allowed because they would resolve differently depending on where the CLI is executed, making security rules non-deterministic and potentially ineffective.

You can use:
- **Absolute paths**: `/mnt/secrets`, `/var/sensitive`
- **Paths with `~`**: `~/private` (expands to `/home/user/private` - becomes absolute)

**Glob Pattern-Based Access Control**

For more fine-grained control, you can use glob patterns to define deny/allow rules:

```yaml
security:
  # Block all files under /etc recursively
  denied_patterns:
    - /etc/**
    - /var/secrets/*
    - ~/private/*.md          # Block all .md files in private directory
    - /tmp/**/secrets/*        # Block secrets directories anywhere under /tmp

  # Allow specific subdirectories even if parent is denied
  # Allowed patterns override denied patterns (higher precedence)
  allowed_patterns:
    - /etc/company-docs/**     # Allow company docs under /etc even if /etc/** is denied
    - ~/private/public/*       # Allow public files in private directory
```

**Glob Pattern Syntax:**
- `*` - Matches any sequence of characters (except `/`)
- `**` - Matches any sequence of characters including `/` (recursive)
- `?` - Matches any single character

**Pattern Precedence:**
1. **Allowed patterns** are checked first - if a path matches an allowed pattern, it's permitted even if it also matches a denied pattern
2. **Denied patterns** are checked second - if a path matches a denied pattern and not an allowed pattern, access is blocked
3. **Literal restricted paths** (from `restricted_paths`) are always checked and cannot be overridden by patterns

**Audit Logging:**
When a denied pattern blocks access, an INFO-level log message is generated for audit purposes:
```
INFO - Blocked access to '/etc/passwd' due to denied pattern '/etc/**'
```

You cannot use:
- **Relative paths**: `secrets`, `../private`, `./config` (will raise `ValueError`)

All paths are normalized (expanded, resolved) before being checked. Paths that exactly match or are subdirectories of any restricted path will be blocked.

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
5. **File Permissions**: Ensure config files have appropriate file permissions (e.g., `chmod 600 ~/.vdb-flow/config.yaml` or `chmod 600 ~/.vdb-flow/config.yml`)

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

## Extensibility

VDB Flow uses a **pluggable adapter registry system** that makes the hexagonal architecture practical and extensible. You can add custom database adapters without modifying core code.

### Creating a Custom Adapter

To create a custom adapter for a new vector database:

1. Implement the `VectorDatabase` interface from `src.database.port`
2. Create a factory function that returns your adapter instance
3. Register it with the adapter registry:

```python
from src.database import register_adapter, VectorDatabase

class MyVectorDatabase(VectorDatabase):
    # Implement all abstract methods...
    pass

def create_my_adapter(**kwargs):
    return MyVectorDatabase(**kwargs)

# Register the adapter
register_adapter("mydb", create_my_adapter)

# Now you can use it
from src.database import create_vector_database
db = create_vector_database("mydb", api_key="...")
```

### Entry Points for Third-Party Packages

Third-party packages can register adapters via setuptools entry points in their `pyproject.toml`:

```toml
[project.entry-points."vdb_flow.adapters"]
pinecone = "vdb_flow_pinecone:register_pinecone_adapter"
```

The entry point should be a callable function that registers the adapter. For example:

```python
# In vdb_flow_pinecone package
from src.database import register_adapter
from .pinecone_adapter import PineconeVectorDatabase

def register_pinecone_adapter():
    """Entry point function that registers the Pinecone adapter."""
    def create_pinecone_adapter(**kwargs):
        return PineconeVectorDatabase(**kwargs)
    register_adapter("pinecone", create_pinecone_adapter)
```

The entry point function will be called automatically when `create_vector_database` is first invoked. This allows adapter packages to be installed separately and automatically discovered.

### Available Adapters

**Built-in Adapters:**

- **`qdrant`**: Production-ready vector database adapter (default). Requires a running Qdrant server.
- **`inmemory`**: In-memory adapter for testing and development. No external dependencies, but data is not persisted.

You can check which adapters are available at runtime:

```python
from src.database import get_available_adapters

print(get_available_adapters())  # ['qdrant', 'inmemory', ...]
```

**Using the In-Memory Adapter:**

The in-memory adapter is useful for:
- Testing without external dependencies
- Development and prototyping
- Demonstrating the pluggable architecture

To use it, set the database type in your config:

```yaml
database:
  type: "inmemory"
```

Or via environment variable:

```bash
export VECTOR_DB_TYPE=inmemory
vdb-flow create test-collection
```

Note: Data stored in the in-memory adapter is lost when the process exits. This adapter is not suitable for production use.
