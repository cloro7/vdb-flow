"""Main CLI entry point."""

import argparse
import logging
import sys

from ..config import get_config
from ..database import create_vector_database
from .commands import CLICommands


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _show_version():
    """Display the version of vdb-manager."""
    try:
        # Try to import version from setuptools_scm generated file
        try:
            from .. import _version

            version_str = _version.version
        except (ImportError, AttributeError):
            # Fallback to importlib.metadata for installed packages
            try:
                from importlib.metadata import version as get_version

                version_str = get_version("vdb-manager")
            except ImportError:
                # Python < 3.8 fallback
                try:
                    from importlib_metadata import version as get_version

                    version_str = get_version("vdb-manager")
                except ImportError:
                    version_str = "unknown"

        print(f"vdb-manager {version_str}")
    except Exception:
        print("vdb-manager unknown")


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

    # Delete command
    delete_parser = subparsers.add_parser(
        "delete", help="Delete an existing collection."
    )
    delete_parser.add_argument("collection", help="Name of the collection to delete.")

    # Clear command
    clear_parser = subparsers.add_parser(
        "clear", help="Remove all vectors from a collection without deleting it."
    )
    clear_parser.add_argument("collection", help="Name of the collection to clear.")

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

    # List command
    subparsers.add_parser("list", help="List all collections.")

    # Get collection info command
    get_info_parser = subparsers.add_parser(
        "info", help="Get information about a collection."
    )
    get_info_parser.add_argument(
        "collection", help="Name of the collection to get information about."
    )

    # Version command
    subparsers.add_parser("version", help="Show the version of vdb-manager.")

    return parser


def _get_commands() -> CLICommands:
    """
    Lazy initialization of CLI commands with database client.

    Only initializes the database stack when actually needed.
    """
    config = get_config()
    db_client = create_vector_database(
        db_type=config.database_type,
        qdrant_url=(
            config.qdrant_url if config.database_type.lower() == "qdrant" else None
        ),
    )
    return CLICommands(db_client)


def main():
    """Execute the main CLI entry point."""
    setup_logging()

    parser = create_parser()
    args = parser.parse_args()

    # Commands that require database access
    db_commands = {"create", "delete", "clear", "list", "info", "load"}

    # Lazy-load database client only for commands that need it
    commands = None
    if args.action in db_commands:
        commands = _get_commands()

    # Route commands
    if args.action == "version":
        _show_version()
        return
    elif args.action == "create":
        # Default to hybrid=True, unless --no-hybrid is specified
        enable_hybrid = not getattr(args, "no_hybrid", False)
        vector_size = getattr(args, "vector_size", None)
        distance_metric = getattr(args, "distance", "Cosine")
        commands.create_collection(
            args.collection,
            distance_metric,
            enable_hybrid=enable_hybrid,
            vector_size=vector_size,
        )
    elif args.action == "delete":
        commands.delete_collection(args.collection)
    elif args.action == "clear":
        commands.clear_collection(args.collection)
    elif args.action == "list":
        commands.list_collections()
    elif args.action == "info":
        commands.get_collection_info(args.collection)
    elif args.action == "load":
        commands.load_collection(args.collection, args.path)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
