"""Main CLI entry point."""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

from ..composition import get_container
from ..config import get_config
from .commands import CLICommands

logger = logging.getLogger(__name__)


def setup_logging(log_level: int = logging.INFO):
    """
    Set up logging configuration.

    Args:
        log_level: Logging level (default: logging.INFO)
    """
    # Configure root logger to ensure all loggers inherit the configuration
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,  # Override any existing configuration
    )
    # Explicitly set level on root logger to ensure all child loggers inherit it
    logging.root.setLevel(log_level)


def _show_version():
    """Display the version of vdb-flow."""
    try:
        # Try to import version from setuptools_scm generated file
        try:
            from .. import _version

            version_str = _version.version
        except (ImportError, AttributeError):
            # Fallback to importlib.metadata for installed packages
            try:
                from importlib.metadata import version as get_version

                version_str = get_version("vdb-flow")
            except ImportError:
                # Python < 3.8 fallback
                try:
                    from importlib_metadata import version as get_version

                    version_str = get_version("vdb-flow")
                except ImportError:
                    version_str = "unknown"

        print(f"vdb-flow {version_str}")
    except Exception:
        print("vdb-flow unknown")


def _add_log_level_argument(parser: argparse.ArgumentParser) -> None:
    """Add --log-level argument to a parser."""
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help=(
            "Set logging verbosity level. If not specified, uses value from config file "
            "(default: INFO). Choices: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
            "Case-insensitive (e.g., 'debug' or 'DEBUG' both work)."
        ),
    )


def _add_output_argument(parser: argparse.ArgumentParser) -> None:
    """Add --output argument to a parser."""
    parser.add_argument(
        "--output",
        type=str.lower,
        choices=["json", "table"],
        default="json",
        help=(
            "Output format (default: json). "
            "Use 'json' for machine-readable JSON output (default, script-friendly). "
            "Use 'table' for human-readable tables."
        ),
    )


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(description="Manage ADR embeddings in Qdrant.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Load command
    load_parser = subparsers.add_parser(
        "load", help="Load ADRs into a Qdrant collection."
    )
    load_parser.add_argument(
        "collection", help="Name of the collection to create or update."
    )
    load_parser.add_argument(
        "path", help="Path to ADR directory (can include subfolders)."
    )
    _add_log_level_argument(load_parser)
    _add_output_argument(load_parser)

    # Delete command
    delete_parser = subparsers.add_parser(
        "delete", help="Delete an existing collection."
    )
    delete_parser.add_argument("collection", help="Name of the collection to delete.")
    _add_log_level_argument(delete_parser)
    _add_output_argument(delete_parser)

    # Clear command
    clear_parser = subparsers.add_parser(
        "clear", help="Remove all vectors from a collection without deleting it."
    )
    clear_parser.add_argument("collection", help="Name of the collection to clear.")
    _add_log_level_argument(clear_parser)
    _add_output_argument(clear_parser)

    # Create command
    create_parser = subparsers.add_parser(
        "create", help="Create a new collection (hybrid search enabled by default)."
    )
    create_parser.add_argument("collection", help="Name of the collection to create.")
    create_parser.add_argument(
        "--distance",
        type=str,
        default="Cosine",
        choices=["Cosine", "Euclid", "Dot"],
        help="Distance metric to use (default: Cosine).",
    )
    create_parser.add_argument(
        "--no-hybrid",
        action="store_true",
        help="Disable hybrid search (use semantic search only).",
    )
    create_parser.add_argument(
        "--vector-size",
        type=int,
        default=None,
        help="Size of embedding vectors (defaults to config value, typically 768).",
    )
    _add_log_level_argument(create_parser)
    _add_output_argument(create_parser)

    # List command
    list_parser = subparsers.add_parser("list", help="List all collections.")
    _add_log_level_argument(list_parser)
    _add_output_argument(list_parser)

    # Get collection info command
    get_info_parser = subparsers.add_parser(
        "info", help="Get information about a collection."
    )
    get_info_parser.add_argument(
        "collection", help="Name of the collection to get information about."
    )
    _add_log_level_argument(get_info_parser)
    _add_output_argument(get_info_parser)

    # Version command
    subparsers.add_parser("version", help="Show the version of vdb-flow.")

    return parser


def _get_commands() -> CLICommands:
    """
    Lazy initialization of CLI commands using composition root.

    Only initializes the database stack when actually needed.
    """
    container = get_container()
    return CLICommands(container.collection_service)


def _print_json(data: Any) -> None:
    """Pretty-print data as JSON."""
    print(json.dumps(data, indent=2))


def _format_list_table(collections: List[Dict[str, Any]]) -> str:
    """
    Format a list of collections as a compact table.

    Args:
        collections: List of collection dictionaries

    Returns:
        Formatted table string
    """
    if not collections:
        return "No collections found."

    # Extract relevant fields (handle different response formats)
    rows = []
    for coll in collections:
        name = coll.get("name", "unknown")
        # Try different field names for point/vector count
        # Use 'in' checks to handle 0 values correctly (0 is falsy but valid)
        if "points_count" in coll:
            points = coll["points_count"]
        elif "vectors_count" in coll:
            points = coll["vectors_count"]
        elif "indexed_vectors_count" in coll:
            points = coll["indexed_vectors_count"]
        else:
            points = 0
        # Try to get status if available
        status = coll.get("status", "active")
        rows.append((name, points, status))

    # Calculate column widths
    name_width = max(len("Name"), max(len(str(name)) for name, _, _ in rows))
    points_width = max(len("Vectors"), max(len(str(points)) for _, points, _ in rows))
    status_width = max(len("Status"), max(len(str(status)) for _, _, status in rows))

    # Build table
    header = f"{'Name':<{name_width}}  {'Vectors':<{points_width}}  {'Status':<{status_width}}"
    separator = "-" * len(header)
    lines = [header, separator]

    for name, points, status in rows:
        lines.append(
            f"{name:<{name_width}}  {points:<{points_width}}  {status:<{status_width}}"
        )

    return "\n".join(lines)


def _format_dict_table(data: Dict[str, Any]) -> str:
    """
    Format a dictionary as a key-value table.

    Args:
        data: Dictionary to format

    Returns:
        Formatted table string
    """
    if not data:
        return "No data available."

    # Flatten nested structures for display
    def flatten_dict(d: Dict[str, Any], prefix: str = "") -> List[tuple]:
        items = []
        for key, value in sorted(d.items()):
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                items.extend(flatten_dict(value, full_key))
            elif isinstance(value, list):
                items.append((full_key, f"[{len(value)} items]"))
            else:
                items.append((full_key, str(value)))
        return items

    items = flatten_dict(data)
    if not items:
        return "No data available."

    # Calculate column widths
    key_width = max(len("Key"), max(len(key) for key, _ in items))
    value_width = min(80, max(len("Value"), max(len(str(val)) for _, val in items)))

    # Build table
    header = f"{'Key':<{key_width}}  {'Value':<{value_width}}"
    separator = "-" * len(header)
    lines = [header, separator]

    for key, value in items:
        # Truncate long values
        if len(value) > value_width:
            value = value[: value_width - 3] + "..."
        lines.append(f"{key:<{key_width}}  {value:<{value_width}}")

    return "\n".join(lines)


def _format_output(data: Any, output_format: str, command: str) -> None:
    """
    Format and print output based on format type.

    Args:
        data: Data to output
        output_format: Format type ("json" or "table")
        command: Command name for context
    """
    if output_format == "json":
        _print_json(data)
    else:
        # Table format
        if isinstance(data, list):
            if command == "list":
                print(_format_list_table(data))
            else:
                # For other list commands, fall back to JSON
                _print_json(data)
        elif isinstance(data, dict):
            print(_format_dict_table(data))
        else:
            # Fall back to JSON for other types
            _print_json(data)


def _extract_collection_name(data: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Extract collection name from data or context."""
    return (
        context.get("collection")
        or data.get("collection")
        or data.get("result", {}).get("name")
        or data.get("name", "unknown")
    )


def _log_create_summary(data: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Log summary for create command."""
    result_block = data.get("result")
    name = None
    vector_size = None
    if isinstance(result_block, dict):
        name = result_block.get("name")
        config = result_block.get("config", {})
        params = config.get("params", {})
        vectors = params.get("vectors", {})
        vector_size = vectors.get("size")
    if not name:
        name = _extract_collection_name(data, context)
    if vector_size:
        logger.info(f"Collection created: name={name}, vector_size={vector_size}")
    else:
        logger.info(f"Collection created: name={name}")


def _log_delete_summary(data: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Log summary for delete command."""
    name = context.get("collection") or data.get("collection", "unknown")
    logger.info(f"Collection deleted: name={name}")


def _log_clear_summary(data: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Log summary for clear command."""
    name = _extract_collection_name(data, context)
    logger.info(f"Collection cleared: name={name}")


def _log_info_summary(data: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Log summary for info command."""
    name = _extract_collection_name(data, context)
    points = data.get("result", {}).get("points_count") or data.get("points_count", 0)
    logger.info(f"Collection info: name={name}, vectors={points}")


def _log_summary(
    data: Any, command: str, context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a one-line summary for command results.

    Args:
        data: Command result data
        command: Command name
        context: Optional context dictionary with additional info (e.g., collection name)
    """
    context = context or {}
    if command == "list":
        if isinstance(data, list):
            logger.info(f"Found {len(data)} collection(s)")
        return

    if not isinstance(data, dict):
        return

    command_handlers = {
        "create": _log_create_summary,
        "delete": _log_delete_summary,
        "clear": _log_clear_summary,
        "info": _log_info_summary,
    }

    handler = command_handlers.get(command)
    if handler:
        handler(data, context)


def _get_log_level_from_args(args: argparse.Namespace) -> int:
    """
    Get logging level from command line arguments, falling back to config or default.

    Args:
        args: Parsed command line arguments

    Returns:
        Logging level constant
    """
    log_level_str = getattr(args, "log_level", None)
    if log_level_str:
        # Convert string to logging level constant (already uppercase from argparse)
        return getattr(logging, log_level_str, logging.INFO)
    # Fallback to config if flag not provided
    try:
        config = get_config()
        return config.log_level
    except Exception:
        # If config loading fails, use default
        return logging.INFO


def _execute_command(args: argparse.Namespace, commands: CLICommands) -> Any:
    """
    Execute the command based on parsed arguments.

    Args:
        args: Parsed command line arguments
        commands: CLICommands instance

    Returns:
        Command result (None for commands that don't return data)
    """
    if args.action == "create":
        # Default to hybrid=True, unless --no-hybrid is specified
        enable_hybrid = not getattr(args, "no_hybrid", False)
        vector_size = getattr(args, "vector_size", None)
        distance_metric = getattr(args, "distance", "Cosine")
        return commands.create_collection(
            args.collection,
            distance_metric,
            enable_hybrid=enable_hybrid,
            vector_size=vector_size,
        )
    elif args.action == "delete":
        return commands.delete_collection(args.collection)
    elif args.action == "clear":
        return commands.clear_collection(args.collection)
    elif args.action == "list":
        return commands.list_collections()
    elif args.action == "info":
        return commands.get_collection_info(args.collection)
    elif args.action == "load":
        return commands.load_collection(args.collection, args.path)
    return None


def main():
    """Execute the main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Handle version command (doesn't need database or config)
    if args.action == "version":
        _show_version()
        return

    # Commands that require database access
    db_commands = {"create", "delete", "clear", "list", "info", "load"}

    # Lazy-load database client only for commands that need it
    if args.action not in db_commands:
        parser.print_help()
        sys.exit(1)

    # Only resolve log level for DB commands (may call get_config())
    log_level = _get_log_level_from_args(args)
    setup_logging(log_level)

    commands = _get_commands()
    result = _execute_command(args, commands)

    # Output result to stdout
    if result is not None:
        summary_context: Optional[Dict[str, Any]] = None
        if args.action in {"info", "create", "delete", "clear"}:
            summary_context = {"collection": args.collection}
        output_format = getattr(args, "output", "json")
        _format_output(result, output_format, args.action)
        # Log summary for command results
        _log_summary(result, args.action, summary_context)


if __name__ == "__main__":
    main()
