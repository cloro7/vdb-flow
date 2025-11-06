"""Validation utilities for security and data integrity."""

import os
import re
from pathlib import Path

# Valid distance metrics for vector databases
VALID_DISTANCE_METRICS = ["Cosine", "Euclid", "Dot"]

# Collection name validation pattern
# Allow alphanumeric, hyphens, underscores, and dots
# Must start with alphanumeric, 1-63 characters (common DB limits)
COLLECTION_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,62}$")


def validate_collection_name(collection_name: str) -> None:
    """
    Validate collection name to prevent injection vulnerabilities.

    Args:
        collection_name: Name to validate

    Raises:
        ValueError: If collection name is invalid
    """
    if not isinstance(collection_name, str):
        raise ValueError("Collection name must be a string")

    if not collection_name:
        raise ValueError("Collection name cannot be empty")

    if not COLLECTION_NAME_PATTERN.match(collection_name):
        raise ValueError(
            f"Invalid collection name '{collection_name}'. "
            f"Collection names must: "
            f"start with alphanumeric, contain only alphanumeric, "
            f"hyphens, underscores, and dots, and be 1-63 characters long."
        )


def validate_distance_metric(distance_metric: str) -> None:
    """
    Validate distance metric value.

    Args:
        distance_metric: Distance metric to validate

    Raises:
        ValueError: If distance metric is invalid
    """
    if not isinstance(distance_metric, str):
        raise ValueError("Distance metric must be a string")

    if distance_metric not in VALID_DISTANCE_METRICS:
        raise ValueError(
            f"Invalid distance metric '{distance_metric}'. "
            f"Valid options are: {', '.join(VALID_DISTANCE_METRICS)}"
        )


def validate_path(path: str, must_exist: bool = True) -> Path:
    """
    Validate and normalize a file system path to prevent directory traversal.

    Args:
        path: Path to validate
        must_exist: Whether the path must exist

    Returns:
        Normalized Path object

    Raises:
        ValueError: If path is invalid or contains traversal attempts
        FileNotFoundError: If path doesn't exist and must_exist is True
    """
    if not isinstance(path, str):
        raise ValueError("Path must be a string")

    if not path:
        raise ValueError("Path cannot be empty")

    # Check for directory traversal attempts in the original path
    # This must be done before path normalization, as abspath/resolve will remove '..'
    if ".." in path:
        raise ValueError(f"Path contains invalid traversal: {path}")

    # Expand user home directory
    expanded_path = os.path.expanduser(path)

    # Convert to absolute path
    abs_path = os.path.abspath(expanded_path)
    path_obj = Path(abs_path)

    # Check for suspicious patterns in resolved path
    try:
        resolved_path = path_obj.resolve(strict=False)
        resolved_str = str(resolved_path)

        # Check for access to system directories
        if resolved_str.startswith("/proc") or resolved_str.startswith("/sys"):
            raise ValueError(f"Path contains invalid traversal: {path}")
    except OSError as e:
        raise ValueError(f"Invalid path: {path}") from e
    except ValueError as e:
        # Re-raise ValueError if it's our specific error message
        if "Path contains invalid traversal" in str(e):
            raise
        raise ValueError(f"Invalid path: {path}") from e

    # Check if path exists if required
    if must_exist and not path_obj.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    return path_obj
