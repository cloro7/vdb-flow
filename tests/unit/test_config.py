"""Unit tests for Config loading, merge, env overrides, and properties."""

import logging
from pathlib import Path

import pytest

import vdb_flow.config as config_module
from vdb_flow.config import Config, get_config


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Isolate tests that use get_config()."""
    config_module._config_instance = None
    yield
    config_module._config_instance = None


@pytest.fixture
def tmp_yaml(tmp_path):
    def _write(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    return _write


class TestConfigFromFile:
    def test_load_yaml_merges_database_url(self, tmp_yaml):
        path = tmp_yaml(
            "cfg.yaml",
            """
database:
  type: inmemory
  url: http://qdrant:6333
embeddings:
  model: custom-model
""",
        )
        c = Config(config_path=path)
        assert c.database_type == "inmemory"
        assert c.qdrant_url == "http://qdrant:6333"
        assert c.embedding_model == "custom-model"

    def test_migrate_qdrant_url_to_database(self, tmp_yaml, caplog):
        path = tmp_yaml(
            "cfg.yaml",
            """
qdrant:
  url: http://legacy:6333
""",
        )
        caplog.set_level(logging.INFO)
        c = Config(config_path=path)
        assert c.qdrant_url == "http://legacy:6333"

    def test_invalid_yaml_logs_warning(self, tmp_yaml, caplog):
        path = tmp_yaml("bad.yaml", "invalid: [\n")
        caplog.set_level(logging.WARNING)
        c = Config(config_path=path)
        assert c.database_type == "qdrant"
        assert "Failed to load config" in caplog.text


class TestConfigEnv:
    def test_env_overrides(self, monkeypatch, tmp_yaml):
        path = tmp_yaml("cfg.yaml", "database:\n  type: qdrant\n")
        monkeypatch.setenv("VECTOR_DB_TYPE", "InMemory")
        monkeypatch.setenv("QDRANT_URL", "http://env:6333")
        monkeypatch.setenv("EMBEDDING_ADAPTER_TYPE", "http_ollama_compat")
        monkeypatch.setenv("EMBEDDING_URL", "http://embed/api")
        monkeypatch.setenv("EMBEDDING_MODEL", "m")
        monkeypatch.setenv("EMBEDDING_TIMEOUT", "42")
        monkeypatch.setenv("VECTOR_SIZE", "384")
        monkeypatch.setenv("CHUNK_SIZE", "256")
        monkeypatch.setenv("CHUNK_OVERLAP", "16")
        monkeypatch.setenv("RATE_LIMITING_DISABLED", "true")
        monkeypatch.setenv("DB_RATE_LIMIT", "5")
        monkeypatch.setenv("EMBEDDING_RATE_LIMIT", "10")
        monkeypatch.setenv("LOG_LEVEL", "debug")
        c = Config(config_path=path)
        assert c.database_type == "inmemory"
        assert c.qdrant_url == "http://env:6333"
        assert c.embedding_adapter_type == "http_ollama_compat"
        assert c.embedding_url == "http://embed/api"
        assert c.embedding_model == "m"
        assert c.embedding_timeout == 42
        assert c.vector_size == 384
        assert c.chunk_size == 256
        assert c.chunk_overlap == 16
        assert c.rate_limiting_disabled is True
        assert c.db_rate_limit == 5
        assert c.embedding_rate_limit == 10
        assert c.log_level == logging.DEBUG

    def test_database_url_fallback_name(self, monkeypatch, tmp_yaml):
        path = tmp_yaml("cfg.yaml", "database:\n  type: qdrant\n")
        monkeypatch.delenv("QDRANT_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "http://db-url:6333")
        c = Config(config_path=path)
        assert c.qdrant_url == "http://db-url:6333"

    def test_invalid_int_env_logs(self, monkeypatch, tmp_yaml, caplog):
        path = tmp_yaml("cfg.yaml", "database:\n  type: qdrant\n")
        monkeypatch.setenv("VECTOR_SIZE", "not-an-int")
        caplog.set_level(logging.WARNING)
        c = Config(config_path=path)
        assert "Invalid VECTOR_SIZE" in caplog.text
        assert isinstance(c.vector_size, int)


class TestConfigProperties:
    def test_qdrant_url_legacy_nested(self):
        c = Config.__new__(Config)
        c._config = {
            "database": {},
            "qdrant": {"url": "http://old-qdrant/"},
            "embeddings": {},
            "text_processing": {},
            "rate_limiting": {},
            "security": {},
            "logging": {},
        }
        assert c.qdrant_url == "http://old-qdrant/"

    def test_log_level_unknown_defaults_to_info(self):
        c = Config.__new__(Config)
        c._config = {
            "database": {},
            "embeddings": {},
            "text_processing": {},
            "rate_limiting": {},
            "security": {},
            "logging": {"level": "NOT_A_LEVEL"},
        }
        assert c.log_level == logging.INFO

    def test_security_lists(self, tmp_yaml):
        path = tmp_yaml(
            "cfg.yaml",
            """
security:
  restricted_paths: ["/tmp/secret"]
  denied_patterns: ["*.key"]
  allowed_patterns: ["/safe/**"]
""",
        )
        c = Config(config_path=path)
        assert c.restricted_paths == ["/tmp/secret"]
        assert c.denied_patterns == ["*.key"]
        assert c.allowed_patterns == ["/safe/**"]


class TestGetConfig:
    def test_get_config_singleton(self, tmp_yaml):
        path = tmp_yaml("cfg.yaml", "database:\n  type: inmemory\n")
        c1 = get_config(path)
        c2 = get_config()
        assert c1 is c2
