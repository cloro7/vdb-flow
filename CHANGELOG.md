# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/cloro7/vdb-manager/compare/v0.1.0...HEAD
