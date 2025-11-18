"""Configuration management for VDB Manager."""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .constants import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_DB_RATE_LIMIT,
    DEFAULT_EMBEDDING_RATE_LIMIT,
    DEFAULT_VECTOR_SIZE,
)

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    "database": {
        "type": "qdrant",  # Options: "qdrant", "inmemory" (for testing/dev), "pinecone", "weaviate", etc.
        "url": "http://localhost:6333",
    },
    "ollama": {
        "url": "http://localhost:11434/api/embeddings",
        "model": "nomic-embed-text:latest",
        "timeout": 60,
        "vector_size": DEFAULT_VECTOR_SIZE,  # Default vector size for embeddings
    },
    "text_processing": {
        "chunk_size": DEFAULT_CHUNK_SIZE,
        "overlap": DEFAULT_CHUNK_OVERLAP,
        "max_text_length": 5000,
    },
    "rate_limiting": {
        "disabled": False,  # Set to True to disable rate limiting (development only)
        "db_requests_per_second": DEFAULT_DB_RATE_LIMIT,  # Database requests per second
        "embedding_requests_per_second": DEFAULT_EMBEDDING_RATE_LIMIT,  # Embedding API requests per second
    },
    "security": {
        # Optional list of additional system directories to block (literal paths)
        # Always-blocked: /proc, /sys, /dev, /run, /var/run (virtual filesystems)
        # Optional (can be added here to block): /etc, /root, /boot, /sbin, /usr/sbin
        "restricted_paths": [],
        # Glob patterns to block (e.g., "/etc/**", "/var/secrets/*")
        # Patterns support standard glob syntax: *, **, ?
        "denied_patterns": [],
        # Glob patterns to explicitly permit, even if they match a denied pattern
        # Allowed patterns override denied patterns (higher precedence)
        "allowed_patterns": [],
    },
}


class Config:
    """Configuration manager that loads from file and environment variables."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config file. If None, looks for config.yaml or config.yml in ~/.vdb-manager/.
        """
        self._config = DEFAULT_CONFIG.copy()

        # Determine config file path
        if config_path is None:
            # Look for config.yaml or config.yml in user's home directory
            home_dir = Path.home()
            config_dir = home_dir / ".vdb-manager"
            # Create directory if it doesn't exist (but don't create the file)
            config_dir.mkdir(mode=0o755, exist_ok=True)

            # Check for both config.yaml and config.yml (prefer .yaml if both exist)
            config_yaml = config_dir / "config.yaml"
            config_yml = config_dir / "config.yml"

            if config_yaml.exists():
                config_path = config_yaml
            elif config_yml.exists():
                config_path = config_yml
            else:
                # Default to config.yaml for logging purposes (even if it doesn't exist)
                config_path = config_yaml

        # Load from file if it exists
        if config_path and config_path.exists():
            self._load_from_file(config_path)
        else:
            logger.debug(f"Config file not found at {config_path}, using defaults")

        # Override with environment variables
        self._load_from_env()

    def _load_from_file(self, config_path: Path) -> None:
        """Load configuration from YAML file."""
        try:
            import yaml

            with open(config_path, "r") as f:
                file_config = yaml.safe_load(f) or {}

            # Handle migration from old structure (qdrant.url) to new structure (database.url)
            if "qdrant" in file_config and "url" in file_config.get("qdrant", {}):
                if "database" not in file_config:
                    file_config["database"] = {}
                # Migrate qdrant.url to database.url if database.url doesn't exist
                if "url" not in file_config.get("database", {}):
                    file_config["database"]["url"] = file_config["qdrant"]["url"]
                    logger.info("Migrated qdrant.url to database.url in configuration")

            # Merge file config with defaults
            self._merge_config(self._config, file_config)
            logger.info(f"Loaded configuration from {config_path}")
        except ImportError:
            logger.warning(
                "PyYAML not installed, cannot load config file. Install with: pip install pyyaml"
            )
        except Exception as e:
            logger.warning(f"Failed to load config file {config_path}: {e}")

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override config into base config."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Database type
        if db_type := os.getenv("VECTOR_DB_TYPE"):
            self._config["database"]["type"] = db_type.lower()

        # Database URL (for Qdrant and other vector databases)
        if db_url := os.getenv("QDRANT_URL") or os.getenv("DATABASE_URL"):
            self._config["database"]["url"] = db_url

        # Ollama settings
        if ollama_url := os.getenv("OLLAMA_URL"):
            self._config["ollama"]["url"] = ollama_url
        if ollama_model := os.getenv("OLLAMA_MODEL"):
            self._config["ollama"]["model"] = ollama_model
        self._set_int_env("OLLAMA_TIMEOUT", "ollama", "timeout")
        self._set_int_env("VECTOR_SIZE", "ollama", "vector_size")

        # Text processing settings
        self._set_int_env("CHUNK_SIZE", "text_processing", "chunk_size")
        self._set_int_env("CHUNK_OVERLAP", "text_processing", "overlap")

        # Rate limiting settings
        if disabled_env := os.getenv("RATE_LIMITING_DISABLED"):
            # Support "true", "1", "yes" (case-insensitive) as truthy values
            self._config["rate_limiting"]["disabled"] = disabled_env.lower() in (
                "true",
                "1",
                "yes",
            )
        self._set_int_env("DB_RATE_LIMIT", "rate_limiting", "db_requests_per_second")
        self._set_int_env(
            "EMBEDDING_RATE_LIMIT", "rate_limiting", "embedding_requests_per_second"
        )

    def _set_int_env(self, env_var: str, section: str, key: str) -> None:
        """Set integer config value from environment variable."""
        if value := os.getenv(env_var):
            try:
                self._config[section][key] = int(value)
            except ValueError:
                logger.warning(f"Invalid {env_var} value: {value}")

    @property
    def database_type(self) -> str:
        """Get database type (e.g., 'qdrant', 'pinecone', 'weaviate')."""
        return self._config["database"]["type"]

    @property
    def qdrant_url(self) -> str:
        """
        Get Qdrant URL.

        Supports both new structure (database.url) and legacy structure (qdrant.url)
        for backward compatibility.
        """
        # Check new structure first
        if "url" in self._config.get("database", {}):
            return self._config["database"]["url"]
        # Fallback to legacy structure for backward compatibility
        if "qdrant" in self._config and "url" in self._config["qdrant"]:
            return self._config["qdrant"]["url"]
        # Default fallback
        return "http://localhost:6333"

    @property
    def ollama_url(self) -> str:
        """Get Ollama URL."""
        return self._config["ollama"]["url"]

    @property
    def ollama_model(self) -> str:
        """Get Ollama model name."""
        return self._config["ollama"]["model"]

    @property
    def ollama_timeout(self) -> int:
        """Get Ollama request timeout."""
        return self._config["ollama"]["timeout"]

    @property
    def vector_size(self) -> int:
        """Get vector size for embeddings."""
        return self._config["ollama"].get("vector_size", DEFAULT_VECTOR_SIZE)

    @property
    def chunk_size(self) -> int:
        """Get text chunk size in words."""
        return self._config["text_processing"]["chunk_size"]

    @property
    def chunk_overlap(self) -> int:
        """Get chunk overlap in words."""
        return self._config["text_processing"]["overlap"]

    @property
    def max_text_length(self) -> int:
        """Get maximum text length for embedding."""
        return self._config["text_processing"]["max_text_length"]

    @property
    def rate_limiting_disabled(self) -> bool:
        """Check if rate limiting is disabled (development only)."""
        return self._config.get("rate_limiting", {}).get("disabled", False)

    @property
    def db_rate_limit(self) -> int:
        """Get database requests per second rate limit."""
        return self._config.get("rate_limiting", {}).get(
            "db_requests_per_second", DEFAULT_DB_RATE_LIMIT
        )

    @property
    def embedding_rate_limit(self) -> int:
        """Get embedding requests per second rate limit."""
        return self._config.get("rate_limiting", {}).get(
            "embedding_requests_per_second", DEFAULT_EMBEDDING_RATE_LIMIT
        )

    @property
    def restricted_paths(self) -> List[str]:
        """
        Get list of additional restricted paths from config.

        Returns:
            List of paths to block (in addition to always-blocked virtual filesystems)
        """
        return self._config.get("security", {}).get("restricted_paths", [])

    @property
    def denied_patterns(self) -> List[str]:
        """
        Get list of denied glob patterns from config.

        Returns:
            List of glob patterns to block
        """
        return self._config.get("security", {}).get("denied_patterns", [])

    @property
    def allowed_patterns(self) -> List[str]:
        """
        Get list of allowed glob patterns from config.

        Returns:
            List of glob patterns to explicitly permit (overrides denied patterns)
        """
        return self._config.get("security", {}).get("allowed_patterns", [])


# Global config instance
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[Path] = None) -> Config:
    """
    Get the global configuration instance.

    Args:
        config_path: Optional path to config file. Only used on first call.

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance
