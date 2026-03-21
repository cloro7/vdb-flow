# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Semantic versioning workflow**: `pyproject.toml` Commitizen `version_provider = "scm"` (tags only, aligned with setuptools-scm) and GitHub Actions workflow **Release** (`release.yml`) to run `cz bump` via `workflow_dispatch` (auto or explicit patch/minor/major).
- `Dockerfile` and CI workflow: **Docker integration tests** run `pytest tests/integration` inside the built image (host networking to Qdrant/Ollama); **GHCR** push runs only after lint, security, unit, venv integration, and Docker tests succeed, on **main** and version tags (`v*`).

### Removed
- Built-in `http_openai_compat` embedding adapter and embedding `api_key` / `EMBEDDING_API_KEY` / `OPENAI_API_KEY` wiring (only used by that adapter). Use `http_ollama_compat` or register a custom adapter via `vdb_flow.embedding_adapters` entry points.

### Added
- Initial release of VDB Manager
- CLI commands for collection management (create, delete, clear, list, info)
- ADR loading with automatic chunking and embedding
- Hybrid search support (semantic + keyword-based)
- Progress bars for long-running operations
- Batch upload support for improved performance
- Parallel embedding generation
- Comprehensive input validation
- Rate limiting for API requests
- Path validation to prevent directory traversal
- File encoding error handling
- Configuration file support with environment variable overrides

### Security
- Collection name validation to prevent injection attacks
- Path validation to prevent directory traversal
- Rate limiting to prevent abuse and DoS attacks
- Network request timeouts and error handling
- SHA256 hashing for deterministic UUIDs with collision handling
- Input validation for distance metrics
