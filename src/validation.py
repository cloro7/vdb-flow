"""Validation utilities for security and data integrity."""

import os
import re
import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Valid distance metrics for vector databases
VALID_DISTANCE_METRICS = ["Cosine", "Euclid", "Dot"]

# Collection name validation pattern
# Allow alphanumeric, hyphens, underscores, and dots
# Must start with alphanumeric, 1-63 characters (common DB limits)
COLLECTION_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,62}$")

# Always-blocked system directories (virtual filesystems that can leak kernel memory,
# device nodes, or sockets - there is never a legitimate ADR directory here)
ALWAYS_RESTRICTED_DIRS = [
    "/proc",  # Process and system information (virtual filesystem)
    "/sys",  # System and kernel information (virtual filesystem)
    "/dev",  # Device files (virtual filesystem)
    "/run",  # Runtime data (may contain sockets, PIDs)
    "/var/run",  # Runtime data (alternative location - check before /run)
]
# Sort by length (longest first) to ensure /var/run is checked before /run
ALWAYS_RESTRICTED_DIRS.sort(key=len, reverse=True)

# Optionally-blocked system directories (can be configured via config)
# These may contain legitimate documentation in some environments
OPTIONAL_RESTRICTED_DIRS = [
    "/etc",  # System configuration files (some teams store docs here)
    "/root",  # Root user home directory
    "/boot",  # Boot files and kernel
    "/sbin",  # System binaries
    "/usr/sbin",  # System binaries
]
# Sort by length (longest first)
OPTIONAL_RESTRICTED_DIRS.sort(key=len, reverse=True)


def _build_restricted_dirs_list(restricted_paths: Optional[List[str]]) -> List[str]:
    """
    Build list of all restricted directories from always-blocked and config.

    Args:
        restricted_paths: Optional list of additional paths to block from config

    Returns:
        Sorted list of restricted directories (longest first)

    Raises:
        ValueError: If any path in restricted_paths is not absolute
    """
    all_restricted_dirs = ALWAYS_RESTRICTED_DIRS.copy()

    # Add all paths from restricted_paths config (both optional and custom)
    if restricted_paths:
        for restricted_path in restricted_paths:
            # Security: Require absolute paths to ensure deterministic behavior
            # Relative paths would resolve differently depending on current working directory,
            # making security rules non-deterministic and potentially ineffective
            expanded = os.path.expanduser(restricted_path)
            if not os.path.isabs(expanded):
                raise ValueError(
                    f"Restricted path '{restricted_path}' must be an absolute path. "
                    f"Relative paths are not allowed in security.restricted_paths for security reasons. "
                    f"Use an absolute path (e.g., '/mnt/secrets') or expand user home (e.g., '~/private' expands to absolute)."
                )

            # Normalize the path: resolve '..' and symlinks
            try:
                normalized_path_obj = Path(expanded)
                normalized = str(normalized_path_obj.resolve(strict=False))
            except OSError:
                # If resolve fails, use the expanded absolute path
                normalized = expanded

            # Only add if not already in the list (avoid duplicates)
            if normalized not in all_restricted_dirs:
                all_restricted_dirs.append(normalized)

    # Sort by length (longest first) for proper matching
    # This ensures more specific paths (e.g., /var/run) are checked before less specific ones (e.g., /run)
    all_restricted_dirs.sort(key=len, reverse=True)
    return all_restricted_dirs


def _normalize_pattern(pattern: str) -> str:
    """
    Normalize a glob pattern for matching.

    Expands ~, makes absolute, and resolves to ensure consistent matching.

    Args:
        pattern: Glob pattern to normalize

    Returns:
        Normalized pattern string
    """
    expanded = os.path.expanduser(pattern)
    # Make absolute if not already
    if not os.path.isabs(expanded):
        expanded = os.path.abspath(expanded)
    # Resolve to handle '..' and symlinks in the pattern itself
    try:
        return str(Path(expanded).resolve(strict=False))
    except OSError:
        # If resolve fails, return the absolute path
        return expanded


def _matches_pattern(path: str, patterns: List[str]) -> Optional[str]:
    """
    Check if a path matches any of the given glob patterns.

    Args:
        path: Path to check
        patterns: List of normalized glob patterns

    Returns:
        First matching pattern if found, None otherwise
    """
    for pattern in patterns:
        if fnmatch(path, pattern):
            return pattern
    return None


def _check_restricted_path(
    path_str: str,
    all_restricted_dirs: List[str],
    restricted_paths: Optional[List[str]],
    warn_on_optional: bool,
) -> None:
    """
    Check if path matches any restricted directory and raise/warn accordingly.

    Args:
        path_str: Path string to check
        all_restricted_dirs: List of all restricted directories (always + config)
        restricted_paths: Original restricted_paths from config (for optional dir checks)
        warn_on_optional: Whether to warn for optional restricted dirs

    Raises:
        ValueError: If path matches a restricted directory
    """
    # Check against all restricted directories (always-blocked + configured)
    for restricted_dir in all_restricted_dirs:
        if path_str == restricted_dir or path_str.startswith(restricted_dir + "/"):
            raise ValueError(
                f"Path resolves to restricted system directory: {path_str}. "
                f"Access to system directories (e.g., {restricted_dir}) is not allowed for security reasons."
            )

    # Check optional restricted dirs (warn if not in restricted_paths config)
    if warn_on_optional:
        for opt_dir in OPTIONAL_RESTRICTED_DIRS:
            if (path_str == opt_dir or path_str.startswith(opt_dir + "/")) and (
                not restricted_paths or opt_dir not in restricted_paths
            ):
                logger.warning(
                    f"Path '{path_str}' points to system directory '{opt_dir}'. "
                    f"This may contain sensitive files. Consider using a different location for ADRs. "
                    f"To block this path, add it to 'restricted_paths' in your config."
                )


def _check_glob_patterns(
    path_str: str,
    denied_patterns: Optional[List[str]],
    allowed_patterns: Optional[List[str]],
) -> None:
    """
    Check if path matches denied/allowed glob patterns.

    Allowed patterns override denied patterns (higher precedence).

    Args:
        path_str: Path string to check
        denied_patterns: Optional list of glob patterns to block
        allowed_patterns: Optional list of glob patterns to explicitly permit

    Raises:
        ValueError: If path matches a denied pattern and not an allowed pattern
    """
    if not denied_patterns and not allowed_patterns:
        return

    # Normalize patterns
    normalized_allowed = (
        [_normalize_pattern(p) for p in allowed_patterns] if allowed_patterns else []
    )
    normalized_denied = (
        [_normalize_pattern(p) for p in denied_patterns] if denied_patterns else []
    )

    # Check allowed patterns first (higher precedence)
    matching_allowed = _matches_pattern(path_str, normalized_allowed)
    if matching_allowed:
        # Path is explicitly allowed, skip denied pattern check
        return

    # Check denied patterns
    matching_denied = _matches_pattern(path_str, normalized_denied)
    if matching_denied:
        # Log for audit trail
        logger.info(
            "Blocked access to '%s' due to denied pattern '%s'",
            path_str,
            matching_denied,
        )
        raise ValueError(
            f"Blocked access to '{path_str}' due to denied pattern '{matching_denied}'. "
            f"To allow this path, add it to 'allowed_patterns' in your config."
        )


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


def validate_path(
    path: str,
    must_exist: bool = True,
    restricted_paths: Optional[List[str]] = None,
    warn_on_optional: bool = True,
    denied_patterns: Optional[List[str]] = None,
    allowed_patterns: Optional[List[str]] = None,
) -> Path:
    """
    Validate and normalize a file system path to prevent directory traversal.

    Allows relative paths (including those with '..') but blocks:
    - Always blocks: /proc, /sys, /dev, /run, /var/run (virtual filesystems)
    - Optionally blocks: /etc, /root, /boot, /sbin, /usr/sbin (configurable)
    - Paths matching denied_patterns (glob patterns)
    - Invalid path formats

    Allowed patterns override denied patterns (higher precedence).

    Args:
        path: Path to validate
        must_exist: Whether the path must exist
        restricted_paths: Optional list of additional paths to block (from config)
        warn_on_optional: If True, log a warning for optional restricted dirs instead of blocking
        denied_patterns: Optional list of glob patterns to block (e.g., "/etc/**", "/var/secrets/*")
        allowed_patterns: Optional list of glob patterns to explicitly permit (overrides denied patterns)

    Returns:
        Normalized Path object

    Raises:
        ValueError: If path is invalid or contains traversal attempts to restricted areas
        FileNotFoundError: If path doesn't exist and must_exist is True
    """
    if not isinstance(path, str):
        raise ValueError("Path must be a string")

    if not path:
        raise ValueError("Path cannot be empty")

    # Expand user home directory
    expanded_path = os.path.expanduser(path)

    # Convert to absolute path (this resolves '..' safely)
    # os.path.abspath uses the current working directory, so it will correctly
    # resolve relative paths including '..' segments
    abs_path = os.path.abspath(expanded_path)
    abs_str = str(abs_path)

    # Build list of all restricted directories to check
    all_restricted_dirs = _build_restricted_dirs_list(restricted_paths)

    # First check: Block always-restricted and configured-optional directories
    # This catches system directories even if resolve() fails or behaves unexpectedly
    _check_restricted_path(
        abs_str, all_restricted_dirs, restricted_paths, warn_on_optional
    )

    path_obj = Path(abs_path)

    # Check for suspicious patterns in resolved path
    resolved_path = None
    try:
        # Resolve the path (even if it doesn't exist, this resolves symlinks and '..')
        resolved_path = path_obj.resolve(strict=False)
        resolved_str = str(resolved_path)

        # Second check: Block access to system directories based on resolved path
        # This catches cases where symlinks might redirect to system directories
        _check_restricted_path(
            resolved_str, all_restricted_dirs, restricted_paths, warn_on_optional
        )

        # Check glob patterns on resolved path (after literal directory checks)
        if denied_patterns or allowed_patterns:
            _check_glob_patterns(resolved_str, denied_patterns, allowed_patterns)

    except OSError:
        # If resolve fails, fall back to absolute path
        # This can happen if the path doesn't exist or there are permission issues
        resolved_path = None
    except ValueError as e:
        # Re-raise ValueError if it's our specific error message
        if "Path resolves to restricted" in str(e) or "Blocked access" in str(e):
            raise
        # For other ValueErrors, fall back to absolute path
        resolved_path = None

    # Use resolved_path if available, otherwise fall back to path_obj (absolute path)
    # The resolved path is the actual filesystem path after resolving symlinks and '..'
    final_path = resolved_path if resolved_path is not None else path_obj

    # Also check glob patterns on absolute path (in case resolve failed)
    if (denied_patterns or allowed_patterns) and resolved_path is None:
        _check_glob_patterns(abs_str, denied_patterns, allowed_patterns)

    # Check if path exists if required
    # For existence check, always use the absolute path (path_obj) because:
    # 1. os.path.abspath correctly resolves '..' based on current working directory
    # 2. path_obj.exists() checks the actual filesystem path
    # 3. resolved_path might be None if resolve() failed
    if must_exist and not path_obj.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    return final_path
