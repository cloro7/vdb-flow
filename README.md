# VDB Manager

A command-line tool for managing Architecture Decision Records (ADRs) in vector databases. This tool enables you to create collections, load ADR markdown files, chunk and embed them, and manage your vector database collections with support for hybrid search (semantic + keyword-based search).

The project uses a hexagonal architecture pattern that allows for easy extension to support different vector database backends. Currently, Qdrant is implemented, but the architecture makes it straightforward to add support for other vector databases.

## Features

- **Collection Management**: Create, delete, clear, list, and inspect vector database collections
- **ADR Loading**: Recursively load ADR markdown files from directories, automatically chunk and embed them
- **Hybrid Search Support**: Create collections with hybrid search enabled (semantic + BM25 keyword search)
- **Embedding Generation**: Uses Ollama with the `nomic-embed-text` model for generating embeddings
- **Extensible Architecture**: Hexagonal architecture with database port/adapter pattern, making it easy to add support for different vector database backends
- **Current Backend**: Qdrant (with support for other backends via adapter pattern)

## Installation

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
vdb-manager create my-adr-collection Cosine
vdb-manager create my-adr-collection Euclid
vdb-manager create my-adr-collection Dot
```

Create a collection with semantic search only (disable hybrid search):

```bash
vdb-manager create my-adr-collection Cosine --no-hybrid
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

## Requirements

- Python 3.x
- Vector database instance (currently Qdrant, default: `http://localhost:6333`)
- Ollama running with `nomic-embed-text` model (default: `http://localhost:11434`)

## Architecture

The project follows a hexagonal architecture pattern that enables extensibility:

- **Ports**: Abstract interfaces in `src/database/port.py` define the contract for vector database operations
- **Adapters**: Concrete implementations in `src/database/adapters/` (currently Qdrant in `qdrant.py`)
- **Services**: Business logic in `src/services/` that work with the abstract port interface
- **CLI**: Command-line interface in `src/cli/`

This architecture allows you to add support for other vector databases (e.g., Pinecone, Weaviate, Milvus) by implementing the `VectorDatabase` port interface in a new adapter, without modifying the core business logic or CLI.

