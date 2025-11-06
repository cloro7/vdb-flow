"""Unit tests for validation utilities."""

import os
import tempfile
import pytest
from pathlib import Path

from src.validation import (
    validate_collection_name,
    validate_distance_metric,
    validate_path,
)


def test_valid_collection_names():
    """Test that valid collection names pass validation."""
    valid_names = [
        "test",
        "test-123",
        "test_123",
        "test.v1",
        "a",
        "a1",
        "test123",
        "Test123",
        "test-collection-name",
        "test_collection_name",
        "test.collection.name",
        "a" * 63,  # Maximum length
    ]
    for name in valid_names:
        # Should not raise
        validate_collection_name(name)


def test_invalid_collection_names_empty():
    """Test that empty collection names raise ValueError."""
    with pytest.raises(ValueError, match="Collection name cannot be empty"):
        validate_collection_name("")


def test_invalid_collection_names_not_string():
    """Test that non-string collection names raise ValueError."""
    with pytest.raises(ValueError, match="Collection name must be a string"):
        validate_collection_name(None)
    with pytest.raises(ValueError, match="Collection name must be a string"):
        validate_collection_name(123)
    with pytest.raises(ValueError, match="Collection name must be a string"):
        validate_collection_name([])


def test_invalid_collection_names_special_chars():
    """Test that collection names with special characters raise ValueError."""
    invalid_names = [
        "test/",
        "../test",
        "test;drop",
        "test' OR '1'='1",
        "-test",  # Doesn't start with alphanumeric
        "_test",  # Doesn't start with alphanumeric
        ".test",  # Doesn't start with alphanumeric
        "test@123",
        "test#123",
        "test$123",
        "test%123",
        "test space",
        "test\ttab",
        "test\nnewline",
    ]
    for name in invalid_names:
        with pytest.raises(ValueError, match="Invalid collection name"):
            validate_collection_name(name)


def test_invalid_collection_names_too_long():
    """Test that collection names exceeding 63 characters raise ValueError."""
    too_long = "a" * 64
    with pytest.raises(ValueError, match="Invalid collection name"):
        validate_collection_name(too_long)


def test_valid_distance_metrics():
    """Test that valid distance metrics pass validation."""
    valid_metrics = ["Cosine", "Euclid", "Dot"]
    for metric in valid_metrics:
        # Should not raise
        validate_distance_metric(metric)


def test_invalid_distance_metrics_not_string():
    """Test that non-string distance metrics raise ValueError."""
    with pytest.raises(ValueError, match="Distance metric must be a string"):
        validate_distance_metric(None)
    with pytest.raises(ValueError, match="Distance metric must be a string"):
        validate_distance_metric(123)
    with pytest.raises(ValueError, match="Distance metric must be a string"):
        validate_distance_metric([])


def test_invalid_distance_metrics_invalid_value():
    """Test that invalid distance metric values raise ValueError."""
    invalid_metrics = [
        "cosine",  # lowercase
        "COSINE",  # uppercase
        "Manhattan",
        "Hamming",
        "L2",
        "L1",
        "",
        "invalid",
    ]
    for metric in invalid_metrics:
        with pytest.raises(ValueError, match="Invalid distance metric"):
            validate_distance_metric(metric)


def test_valid_path_exists():
    """Test that valid existing paths pass validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        # Should not raise and return Path object
        result = validate_path(str(test_file), must_exist=True)
        assert isinstance(result, Path)
        assert result.exists()


def test_valid_path_directory_exists():
    """Test that valid existing directories pass validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Should not raise and return Path object
        result = validate_path(tmpdir, must_exist=True)
        assert isinstance(result, Path)
        assert result.is_dir()


def test_valid_path_not_exists_must_exist_false():
    """Test that non-existent paths pass when must_exist=False."""
    non_existent = "/tmp/non-existent-path-12345"
    # Should not raise
    result = validate_path(non_existent, must_exist=False)
    assert isinstance(result, Path)


def test_invalid_path_not_exists_must_exist_true():
    """Test that non-existent paths raise FileNotFoundError when must_exist=True."""
    non_existent = "/tmp/non-existent-path-12345"
    with pytest.raises(FileNotFoundError, match="Path does not exist"):
        validate_path(non_existent, must_exist=True)


def test_invalid_path_empty():
    """Test that empty paths raise ValueError."""
    with pytest.raises(ValueError, match="Path cannot be empty"):
        validate_path("", must_exist=False)


def test_invalid_path_not_string():
    """Test that non-string paths raise ValueError."""
    with pytest.raises(ValueError, match="Path must be a string"):
        validate_path(None, must_exist=False)
    with pytest.raises(ValueError, match="Path must be a string"):
        validate_path(123, must_exist=False)
    with pytest.raises(ValueError, match="Path must be a string"):
        validate_path([], must_exist=False)


def test_invalid_path_traversal_attempts():
    """Test that path traversal attempts raise ValueError."""
    traversal_paths = [
        "../../../../../../../../../../etc/passwd",
        "../test",
        "../../test",
        "test/../../etc/passwd",
        "./../test",
        "test/../test",
    ]
    for path in traversal_paths:
        with pytest.raises(ValueError, match="Path contains invalid traversal"):
            validate_path(path, must_exist=False)


def test_invalid_path_system_directories():
    """Test that paths to system directories raise ValueError."""
    system_paths = [
        "/proc/cpuinfo",
        "/sys/kernel",
        "/proc/self",
    ]
    for path in system_paths:
        with pytest.raises(ValueError, match="Path contains invalid traversal"):
            validate_path(path, must_exist=False)


def test_valid_path_home_expansion():
    """Test that ~ expansion works correctly."""
    # Should not raise when must_exist=False
    result = validate_path("~/test-file-12345", must_exist=False)
    assert isinstance(result, Path)
    # Result should be absolute path
    assert result.is_absolute()


def test_valid_path_relative_to_current():
    """Test that relative paths are converted to absolute."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            # Relative path should be converted to absolute
            result = validate_path("test.txt", must_exist=True)
            assert isinstance(result, Path)
            assert result.is_absolute()
            assert result.exists()
        finally:
            os.chdir(original_cwd)
