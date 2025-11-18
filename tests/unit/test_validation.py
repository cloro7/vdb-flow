"""Unit tests for validation utilities."""

import os
import logging
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
    valid_names = ["test", "test-123", "test_123", "test.v1", "my-collection"]
    for name in valid_names:
        validate_collection_name(name)  # Should not raise


def test_invalid_collection_names_not_string():
    """Test that non-string collection names raise ValueError."""
    invalid_names = [None, 123, [], {}]
    for name in invalid_names:
        with pytest.raises(ValueError, match="Collection name must be a string"):
            validate_collection_name(name)


def test_invalid_collection_names_empty():
    """Test that empty collection names raise ValueError."""
    with pytest.raises(ValueError, match="Collection name cannot be empty"):
        validate_collection_name("")


def test_invalid_collection_names_special_chars():
    """Test that collection names with special characters raise ValueError."""
    invalid_names = [
        "test/",
        "../test",
        "test;drop",
        "test@name",
        "test name",  # spaces
        "-test",  # starts with hyphen
        ".test",  # starts with dot
    ]
    for name in invalid_names:
        with pytest.raises(ValueError, match="Invalid collection name"):
            validate_collection_name(name)


def test_valid_distance_metrics():
    """Test that valid distance metrics pass validation."""
    valid_metrics = ["Cosine", "Euclid", "Dot"]
    for metric in valid_metrics:
        validate_distance_metric(metric)  # Should not raise


def test_invalid_distance_metrics():
    """Test that invalid distance metrics raise ValueError."""
    invalid_metrics = ["cosine", "EUCLID", "Manhattan", "invalid", ""]
    for metric in invalid_metrics:
        with pytest.raises(ValueError, match="Invalid distance metric"):
            validate_distance_metric(metric)


def test_valid_paths():
    """Test that valid paths pass validation."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test absolute path
            validate_path(tmpdir, must_exist=True)

            # Test relative path
            os.chdir(tmpdir)
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            validate_path("subdir", must_exist=True)

            # Test path with must_exist=False
            validate_path("/tmp", must_exist=False)
    finally:
        os.chdir(original_cwd)


def test_valid_relative_paths_with_traversal():
    """Test that relative paths with '..' are allowed when they resolve safely."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        try:
            # Create nested directory structure
            nested = Path(tmpdir) / "level1" / "level2"
            nested.mkdir(parents=True)

            # Change to nested directory
            os.chdir(Path(tmpdir) / "level1")

            # Path going up one level should be valid
            parent_path = "../level1"
            result = validate_path(parent_path, must_exist=True)
            assert isinstance(result, Path)
            assert result.is_absolute()
            assert result.exists()

            # Path going up multiple levels should be valid
            root_path = "../../"
            result = validate_path(root_path, must_exist=True)
            assert isinstance(result, Path)
            assert result.is_absolute()
            assert result.exists()
        finally:
            os.chdir(original_cwd)


def test_invalid_path_not_string():
    """Test that non-string paths raise ValueError."""
    invalid_paths = [None, 123, [], {}]
    for path in invalid_paths:
        with pytest.raises(ValueError, match="Path must be a string"):
            validate_path(path, must_exist=False)


def test_invalid_path_empty():
    """Test that empty paths raise ValueError."""
    with pytest.raises(ValueError, match="Path cannot be empty"):
        validate_path("", must_exist=False)


def test_invalid_path_not_exists():
    """Test that non-existent paths raise FileNotFoundError when must_exist=True."""
    with pytest.raises(FileNotFoundError, match="Path does not exist"):
        validate_path("/nonexistent/path/12345", must_exist=True)


def test_invalid_path_system_directories():
    """Test that paths to always-restricted system directories raise ValueError."""
    # Always-blocked virtual filesystems
    always_blocked_paths = [
        "/proc/cpuinfo",
        "/sys/kernel",
        "/proc/self",
        "/dev/null",
        "/run/systemd",
    ]
    for path in always_blocked_paths:
        with pytest.raises(
            ValueError, match="Path resolves to restricted system directory"
        ):
            validate_path(path, must_exist=False)


def test_optional_restricted_paths_warning(caplog):
    """Test that optional restricted paths generate warnings by default."""
    # Optional paths should warn but not block by default
    optional_paths = [
        "/etc/passwd",
        "/root/.bashrc",
        "/boot/vmlinuz",
        "/sbin/init",
        "/usr/sbin/useradd",
    ]

    # Enable logging capture
    with caplog.at_level(logging.WARNING):
        for path in optional_paths:
            # Should not raise, but should log warnings
            result = validate_path(path, must_exist=False, warn_on_optional=True)
            assert isinstance(result, Path)

        # Check that warnings were logged
        assert len(caplog.records) > 0, "Expected at least one warning to be logged"
        assert any(
            "points to system directory" in record.message for record in caplog.records
        )


def test_optional_restricted_paths_blocked():
    """Test that optional restricted paths are blocked when in restricted_paths config."""
    # When paths are in restricted_paths, they should be blocked
    restricted_config = ["/etc", "/root", "/boot"]

    blocked_paths = [
        "/etc/passwd",
        "/root/.bashrc",
        "/boot/vmlinuz",
    ]

    for path in blocked_paths:
        with pytest.raises(
            ValueError, match="Path resolves to restricted system directory"
        ):
            validate_path(path, must_exist=False, restricted_paths=restricted_config)


def test_paths_with_similar_prefixes_allowed():
    """Test that paths with similar prefixes to restricted dirs are allowed."""
    # These paths share prefixes with restricted directories but should be allowed
    # because they're not actually subdirectories of the restricted dirs
    similar_prefix_paths = [
        "/etcetera/docs",  # Shares prefix with /etc but is different directory
        "/procurement/adrs",  # Shares prefix with /proc but is different directory
        "/systematic/notes",  # Shares prefix with /sys but is different directory
        "/development/code",  # Shares prefix with /dev but is different directory
        "/running/scripts",  # Shares prefix with /run but is different directory
    ]

    for path in similar_prefix_paths:
        # Should not raise ValueError (but may warn if it's an optional restricted dir)
        result = validate_path(path, must_exist=False, warn_on_optional=False)
        assert isinstance(result, Path)
        assert result.is_absolute()


def test_custom_restricted_paths():
    """Test that custom paths in restricted_paths config are blocked."""
    # Custom paths that are not in OPTIONAL_RESTRICTED_DIRS should still be blocked
    custom_restricted_paths = [
        "/mnt/secrets",
        "/home/user/private",
        "/tmp/sensitive",
    ]

    for custom_path in custom_restricted_paths:
        # Should raise ValueError when the custom path is in restricted_paths
        with pytest.raises(
            ValueError, match="Path resolves to restricted system directory"
        ):
            validate_path(
                custom_path,
                must_exist=False,
                restricted_paths=[custom_path],
            )

        # Should also block subdirectories of custom restricted paths
        subdir = f"{custom_path}/subdir"
        with pytest.raises(
            ValueError, match="Path resolves to restricted system directory"
        ):
            validate_path(
                subdir,
                must_exist=False,
                restricted_paths=[custom_path],
            )

        # Should allow the path if it's not in restricted_paths
        result = validate_path(custom_path, must_exist=False, restricted_paths=[])
        assert isinstance(result, Path)
        assert result.is_absolute()


def test_custom_restricted_paths_normalization():
    """Test that custom restricted paths are normalized correctly."""
    import tempfile
    from pathlib import Path as PathLib

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with absolute path (should work)
        abs_secrets = str(PathLib(tmpdir) / "secrets")

        # Should block the absolute path when it's in restricted_paths
        with pytest.raises(
            ValueError, match="Path resolves to restricted system directory"
        ):
            validate_path(
                abs_secrets,
                must_exist=False,
                restricted_paths=[abs_secrets],  # Absolute path in config
            )

        # Test with path containing ~ (should expand user home to absolute)
        home_secrets = "~/secrets"
        abs_home_secrets = os.path.expanduser(home_secrets)
        abs_home_secrets = os.path.abspath(abs_home_secrets)

        with pytest.raises(
            ValueError, match="Path resolves to restricted system directory"
        ):
            validate_path(
                abs_home_secrets,
                must_exist=False,
                restricted_paths=[home_secrets],  # Path with ~ expands to absolute
            )


def test_restricted_paths_requires_absolute():
    """Test that restricted_paths must contain only absolute paths."""
    # Relative paths should raise ValueError
    relative_paths = [
        "secrets",
        "../private",
        "docs/sensitive",
        "./config",
    ]

    for relative_path in relative_paths:
        with pytest.raises(ValueError, match="must be an absolute path"):
            validate_path(
                "/some/path",
                must_exist=False,
                restricted_paths=[relative_path],
            )

    # Absolute paths should work
    absolute_paths = [
        "/mnt/secrets",
        "/home/user/private",
        "~/secrets",  # ~ expands to absolute
    ]

    for abs_path in absolute_paths:
        # Should not raise ValueError about path format
        # (may raise other errors, but not about absolute path requirement)
        try:
            validate_path(
                "/some/other/path",
                must_exist=False,
                restricted_paths=[abs_path],
            )
        except ValueError as e:
            # If it's about absolute path requirement, that's wrong
            assert "must be an absolute path" not in str(
                e
            ), f"Absolute path {abs_path} was rejected"


def test_path_with_tilde_expansion():
    """Test that paths with ~ are expanded correctly."""
    home_dir = Path.home()
    # This should expand ~ to the home directory
    expanded = validate_path("~", must_exist=True)
    assert expanded == home_dir or str(expanded) == str(home_dir)


def test_path_normalization():
    """Test that paths are normalized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")

        # Path with redundant separators should normalize
        normalized = validate_path(f"{tmpdir}//test.txt", must_exist=True)
        assert normalized == test_file
