"""Main CLI entry point."""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database import QdrantVectorDatabase
from src.cli.commands import CLICommands


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(description="Manage ADR embeddings in Qdrant.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Load command
    load_parser = subparsers.add_parser("load", help="Load ADRs into a Qdrant collection.")
    load_parser.add_argument("collection", help="Name of the collection to create or update.")
    load_parser.add_argument("path", help="Path to ADR directory (can include subfolders).")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an existing collection.")
    delete_parser.add_argument("collection", help="Name of the collection to delete.")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Remove all vectors from a collection without deleting it.")
    clear_parser.add_argument("collection", help="Name of the collection to clear.")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new collection (hybrid search enabled by default).")
    create_parser.add_argument("collection", help="Name of the collection to create.")
    create_parser.add_argument("distance", nargs='?', default="Cosine", help="Distance metric to use (Cosine, Euclid, Dot).")
    create_parser.add_argument("--no-hybrid", action="store_true", help="Disable hybrid search (use semantic search only).")

    # List command
    list_parser = subparsers.add_parser("list", help="List all collections.")

    # Get collection info command
    get_info_parser = subparsers.add_parser("info", help="Get information about a collection.")
    get_info_parser.add_argument("collection", help="Name of the collection to get information about.")

    return parser


def main():
    """Main CLI entry point."""
    setup_logging()
    
    parser = create_parser()
    args = parser.parse_args()
    
    # Initialize database client and CLI commands
    db_client = QdrantVectorDatabase()
    commands = CLICommands(db_client)
    
    # Route commands
    if args.action == "create":
        # Default to hybrid=True, unless --no-hybrid is specified
        enable_hybrid = not getattr(args, 'no_hybrid', False)
        commands.create_collection(args.collection, args.distance, enable_hybrid=enable_hybrid)
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

