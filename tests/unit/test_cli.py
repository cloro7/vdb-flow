"""Unit tests for CLI commands and argument parsing."""

import pytest
from unittest.mock import Mock, patch

from src.cli.main import create_parser
from src.cli.commands import CLICommands


def test_create_parser_has_all_commands():
    """Test that parser has all expected commands."""
    parser = create_parser()
    subparsers = parser._subparsers._actions[1]

    # Check all commands exist
    assert "create" in subparsers.choices
    assert "delete" in subparsers.choices
    assert "clear" in subparsers.choices
    assert "list" in subparsers.choices
    assert "info" in subparsers.choices
    assert "load" in subparsers.choices


def test_create_command_required_args():
    """Test create command requires collection name."""
    parser = create_parser()

    # Should succeed with collection name
    args = parser.parse_args(["create", "test-collection"])
    assert args.collection == "test-collection"
    assert args.distance == "Cosine"  # Default
    assert args.no_hybrid is False
    assert args.vector_size is None


def test_create_command_with_all_options():
    """Test create command with all valid options."""
    parser = create_parser()

    args = parser.parse_args(
        [
            "create",
            "test-collection",
            "--distance",
            "Euclid",
            "--vector-size",
            "1024",
            "--no-hybrid",
        ]
    )

    assert args.collection == "test-collection"
    assert args.distance == "Euclid"
    assert args.vector_size == 1024
    assert args.no_hybrid is True


def test_create_command_invalid_distance():
    """Test create command rejects invalid distance metric."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["create", "test-collection", "--distance", "Invalid"])


def test_create_command_invalid_vector_size_type():
    """Test create command rejects non-integer vector size."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            ["create", "test-collection", "--vector-size", "not-a-number"]
        )


def test_create_command_zero_vector_size():
    """Test create command accepts zero vector size (validation happens in service)."""
    parser = create_parser()

    # Parser should accept it (type checking only)
    args = parser.parse_args(["create", "test-collection", "--vector-size", "0"])
    assert args.vector_size == 0


def test_delete_command():
    """Test delete command parsing."""
    parser = create_parser()

    args = parser.parse_args(["delete", "test-collection"])
    assert args.collection == "test-collection"


def test_delete_command_missing_collection():
    """Test delete command requires collection name."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["delete"])


def test_clear_command():
    """Test clear command parsing."""
    parser = create_parser()

    args = parser.parse_args(["clear", "test-collection"])
    assert args.collection == "test-collection"


def test_list_command():
    """Test list command parsing (no arguments)."""
    parser = create_parser()

    args = parser.parse_args(["list"])
    assert args.action == "list"


def test_list_command_with_unexpected_args():
    """Test list command rejects unexpected arguments."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["list", "unexpected-arg"])


def test_info_command():
    """Test info command parsing."""
    parser = create_parser()

    args = parser.parse_args(["info", "test-collection"])
    assert args.collection == "test-collection"


def test_load_command():
    """Test load command parsing."""
    parser = create_parser()

    args = parser.parse_args(["load", "test-collection", "/path/to/adrs"])
    assert args.collection == "test-collection"
    assert args.path == "/path/to/adrs"


def test_load_command_missing_args():
    """Test load command requires both collection and path."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["load", "test-collection"])

    with pytest.raises(SystemExit):
        parser.parse_args(["load"])


def test_create_command_unexpected_option():
    """Test create command rejects unexpected options."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["create", "test-collection", "--unexpected-option", "value"])


def test_delete_command_unexpected_option():
    """Test delete command rejects unexpected options."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["delete", "test-collection", "--unexpected-option"])


def test_clear_command_unexpected_option():
    """Test clear command rejects unexpected options."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["clear", "test-collection", "--unexpected-option"])


def test_info_command_unexpected_option():
    """Test info command rejects unexpected options."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["info", "test-collection", "--unexpected-option"])


def test_load_command_unexpected_option():
    """Test load command rejects unexpected options."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            ["load", "test-collection", "/path/to/adrs", "--unexpected-option"]
        )


def test_all_distance_metrics():
    """Test all valid distance metrics are accepted."""
    parser = create_parser()

    for metric in ["Cosine", "Euclid", "Dot"]:
        args = parser.parse_args(["create", "test-collection", "--distance", metric])
        assert args.distance == metric


def test_create_command_defaults():
    """Test create command has correct defaults."""
    parser = create_parser()

    args = parser.parse_args(["create", "test-collection"])
    assert args.distance == "Cosine"
    assert args.no_hybrid is False
    assert args.vector_size is None


def test_create_collection_defaults():
    """Test create_collection with default parameters."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_result = {"result": {"name": "test-collection"}}
    commands.collection_service.create_collection = Mock(return_value=mock_result)

    commands.create_collection("test-collection")

    commands.collection_service.create_collection.assert_called_once_with(
        "test-collection", "Cosine", enable_hybrid=True, vector_size=None
    )


def test_create_collection_with_all_options():
    """Test create_collection with all options specified."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_result = {"result": {"name": "test-collection"}}
    commands.collection_service.create_collection = Mock(return_value=mock_result)

    commands.create_collection(
        "test-collection",
        distance_metric="Euclid",
        enable_hybrid=False,
        vector_size=1024,
    )

    commands.collection_service.create_collection.assert_called_once_with(
        "test-collection", "Euclid", enable_hybrid=False, vector_size=1024
    )


def test_create_collection_invalid_vector_size_zero():
    """Test create_collection raises ValueError for zero vector size."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    commands.collection_service.create_collection = Mock(
        side_effect=ValueError("vector_size must be positive, got 0")
    )

    with pytest.raises(ValueError, match="vector_size must be positive"):
        commands.create_collection("test-collection", vector_size=0)


def test_create_collection_invalid_vector_size_negative():
    """Test create_collection raises ValueError for negative vector size."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    commands.collection_service.create_collection = Mock(
        side_effect=ValueError("vector_size must be positive, got -256")
    )

    with pytest.raises(ValueError, match="vector_size must be positive"):
        commands.create_collection("test-collection", vector_size=-256)


def test_delete_collection():
    """Test delete_collection command."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    # Mock the collection_service method
    commands.collection_service.delete_collection = Mock()

    commands.delete_collection("test-collection")

    commands.collection_service.delete_collection.assert_called_once_with(
        "test-collection"
    )


def test_clear_collection():
    """Test clear_collection command."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_result = {"result": {"status": "cleared"}}
    commands.collection_service.clear_collection = Mock(return_value=mock_result)

    commands.clear_collection("test-collection")

    commands.collection_service.clear_collection.assert_called_once_with(
        "test-collection"
    )


def test_list_collections():
    """Test list_collections command."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_collections = [{"name": "collection1"}, {"name": "collection2"}]
    commands.collection_service.list_collections = Mock(return_value=mock_collections)

    commands.list_collections()

    commands.collection_service.list_collections.assert_called_once()


def test_get_collection_info():
    """Test get_collection_info command."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_info = {"result": {"name": "test-collection", "points_count": 100}}
    commands.collection_service.get_collection_info = Mock(return_value=mock_info)

    commands.get_collection_info("test-collection")

    commands.collection_service.get_collection_info.assert_called_once_with(
        "test-collection"
    )


@patch("src.services.collection.validate_path")
@patch("src.cli.commands.os.path.exists")
@patch("src.cli.commands.os.path.expanduser")
def test_load_collection_success(mock_expanduser, mock_exists, mock_validate_path):
    """Test load_collection with valid path."""
    from pathlib import Path

    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_expanduser.return_value = "/expanded/path"
    mock_exists.return_value = True
    mock_validate_path.return_value = Path("/expanded/path")
    commands.collection_service.load_collection = Mock()

    commands.load_collection("test-collection", "~/path/to/adrs")

    mock_expanduser.assert_called_once_with("~/path/to/adrs")
    mock_exists.assert_called_once_with("/expanded/path")
    commands.collection_service.load_collection.assert_called_once_with(
        "test-collection", "/expanded/path"
    )


@patch("src.cli.commands.os.path.exists")
@patch("src.cli.commands.os.path.expanduser")
def test_load_collection_path_not_found(mock_expanduser, mock_exists):
    """Test load_collection exits when path doesn't exist."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    # Mock the service method to ensure it's not called
    commands.collection_service.load_collection = Mock()

    mock_expanduser.return_value = "/nonexistent/path"
    mock_exists.return_value = False

    # sys.exit raises SystemExit, so we catch it to verify the behavior
    with pytest.raises(SystemExit) as exc_info:
        commands.load_collection("test-collection", "/nonexistent/path")

    # Verify exit code is 1
    assert exc_info.value.code == 1
    # Verify service method was not called since we exit early
    commands.collection_service.load_collection.assert_not_called()


@patch("src.services.collection.validate_path")
@patch("src.cli.commands.os.path.exists")
@patch("src.cli.commands.os.path.expanduser")
@patch("src.cli.commands.sys.exit")
def test_load_collection_value_error(
    mock_exit, mock_expanduser, mock_exists, mock_validate_path
):
    """Test load_collection exits on ValueError (e.g., collection doesn't exist)."""
    from pathlib import Path

    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_validate_path.return_value = Path("/valid/path")
    mock_expanduser.return_value = "/valid/path"
    mock_exists.return_value = True
    commands.collection_service.load_collection = Mock(
        side_effect=ValueError("Collection does not exist")
    )

    commands.load_collection("test-collection", "/valid/path")

    mock_exit.assert_called_once_with(1)
    commands.collection_service.load_collection.assert_called_once()


@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
@patch("src.cli.main.CLICommands")
def test_main_create_command(mock_commands_class, mock_get_config, mock_create_db):
    """Test main function routes create command correctly."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    mock_commands = Mock()
    mock_commands_class.return_value = mock_commands

    # Mock sys.argv
    with patch("sys.argv", ["vdb-manager", "create", "test-collection"]):
        main()

    # Verify create_collection was called with defaults
    mock_commands.create_collection.assert_called_once_with(
        "test-collection", "Cosine", enable_hybrid=True, vector_size=None
    )


@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
@patch("src.cli.main.CLICommands")
def test_main_create_command_with_options(
    mock_commands_class, mock_get_config, mock_create_db
):
    """Test main function routes create command with all options."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    mock_commands = Mock()
    mock_commands_class.return_value = mock_commands

    # Mock sys.argv with all options
    with patch(
        "sys.argv",
        [
            "vdb-manager",
            "create",
            "test-collection",
            "--distance",
            "Euclid",
            "--vector-size",
            "1024",
            "--no-hybrid",
        ],
    ):
        main()

    # Verify create_collection was called with all options
    mock_commands.create_collection.assert_called_once_with(
        "test-collection", "Euclid", enable_hybrid=False, vector_size=1024
    )


@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
@patch("src.cli.main.CLICommands")
def test_main_delete_command(mock_commands_class, mock_get_config, mock_create_db):
    """Test main function routes delete command."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    mock_commands = Mock()
    mock_commands_class.return_value = mock_commands

    # Mock sys.argv
    with patch("sys.argv", ["vdb-manager", "delete", "test-collection"]):
        main()

    mock_commands.delete_collection.assert_called_once_with("test-collection")


@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
@patch("src.cli.main.CLICommands")
def test_main_list_command(mock_commands_class, mock_get_config, mock_create_db):
    """Test main function routes list command."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    mock_commands = Mock()
    mock_commands_class.return_value = mock_commands

    # Mock sys.argv
    with patch("sys.argv", ["vdb-manager", "list"]):
        main()

    mock_commands.list_collections.assert_called_once()


@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
@patch("src.cli.main.CLICommands")
def test_main_info_command(mock_commands_class, mock_get_config, mock_create_db):
    """Test main function routes info command."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    mock_commands = Mock()
    mock_commands_class.return_value = mock_commands

    # Mock sys.argv
    with patch("sys.argv", ["vdb-manager", "info", "test-collection"]):
        main()

    mock_commands.get_collection_info.assert_called_once_with("test-collection")


@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
@patch("src.cli.main.CLICommands")
def test_main_load_command(mock_commands_class, mock_get_config, mock_create_db):
    """Test main function routes load command."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    mock_commands = Mock()
    mock_commands_class.return_value = mock_commands

    # Mock sys.argv
    with patch("sys.argv", ["vdb-manager", "load", "test-collection", "/path/to/adrs"]):
        main()

    mock_commands.load_collection.assert_called_once_with(
        "test-collection", "/path/to/adrs"
    )


@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
@patch("src.cli.main.sys.exit")
def test_main_invalid_command(mock_exit, mock_get_config, mock_create_db):
    """Test main function handles invalid command."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    # Mock sys.argv with invalid command
    with patch("sys.argv", ["vdb-manager", "invalid-command"]):
        try:
            main()
        except SystemExit:
            pass  # argparse raises SystemExit, which we're mocking

    # argparse calls sys.exit(2) for invalid arguments, and may call it multiple times
    # Just verify it was called (at least once)
    assert mock_exit.called


def test_version_command():
    """Test version command parsing."""
    parser = create_parser()

    args = parser.parse_args(["version"])
    assert args.action == "version"


@patch("src.cli.main._show_version")
@patch("src.cli.main.create_vector_database")
@patch("src.cli.main.get_config")
def test_main_version_command(mock_get_config, mock_create_db, mock_show_version):
    """Test main function routes version command."""
    from src.cli.main import main

    # Setup mocks
    mock_config = Mock()
    mock_config.database_type = "qdrant"
    mock_config.qdrant_url = "http://localhost:6333"
    mock_get_config.return_value = mock_config

    mock_db_client = Mock()
    mock_create_db.return_value = mock_db_client

    # Mock sys.argv
    with patch("sys.argv", ["vdb-manager", "version"]):
        main()

    mock_show_version.assert_called_once()
