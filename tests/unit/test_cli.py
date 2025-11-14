"""Unit tests for CLI commands and argument parsing."""

import pytest
from unittest.mock import Mock, patch

from src.cli.main import (
    create_parser,
    _format_list_table,
    _format_dict_table,
    _format_output,
    _log_summary,
)
from src.cli.commands import CLICommands
from src.database.port import InvalidVectorSizeError


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


def test_create_collection_logs_success(caplog):
    """Ensure create_collection logs success message."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)
    commands.collection_service.create_collection = Mock(return_value={})

    with caplog.at_level("INFO"):
        commands.create_collection("test-collection")

    assert "Successfully created collection 'test-collection'" in caplog.text


def test_create_collection_invalid_vector_size_zero():
    """Test create_collection exits with SystemExit for zero vector size."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    commands.collection_service.create_collection = Mock(
        side_effect=InvalidVectorSizeError(
            "vector_size must be positive, got 0. Vector dimensions must be greater than zero."
        )
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.create_collection("test-collection", vector_size=0)

    assert exc_info.value.code == 1


def test_create_collection_invalid_vector_size_negative():
    """Test create_collection exits with SystemExit for negative vector size."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    commands.collection_service.create_collection = Mock(
        side_effect=InvalidVectorSizeError(
            "vector_size must be positive, got -256. Vector dimensions must be greater than zero."
        )
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.create_collection("test-collection", vector_size=-256)

    assert exc_info.value.code == 1


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


def test_delete_collection_logs_success(caplog):
    """Ensure delete_collection logs success message."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)
    commands.collection_service.delete_collection = Mock()

    with caplog.at_level("INFO"):
        commands.delete_collection("test-collection")

    assert "Successfully deleted collection 'test-collection'" in caplog.text


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


def test_clear_collection_logs_success(caplog):
    """Ensure clear_collection logs success message."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)
    commands.collection_service.clear_collection = Mock(return_value={})

    with caplog.at_level("INFO"):
        commands.clear_collection("test-collection")

    assert "Successfully cleared collection 'test-collection'" in caplog.text


def test_list_collections(caplog):
    """Test list_collections command."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_collections = [{"name": "collection1"}, {"name": "collection2"}]
    commands.collection_service.list_collections = Mock(return_value=mock_collections)

    with caplog.at_level("DEBUG"):
        result = commands.list_collections()

    assert "Listing collections..." in caplog.text
    assert result == mock_collections
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


def test_get_collection_info_logs_success(caplog):
    """Ensure get_collection_info logs success message."""
    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)
    commands.collection_service.get_collection_info = Mock(return_value={})

    with caplog.at_level("INFO"):
        commands.get_collection_info("test-collection")

    assert (
        "Successfully retrieved information for collection 'test-collection'"
        in caplog.text
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


@patch("src.services.collection.validate_path")
@patch("src.cli.commands.os.path.exists")
@patch("src.cli.commands.os.path.expanduser")
def test_load_collection_logs_success(
    mock_expanduser, mock_exists, mock_validate_path, caplog
):
    """Ensure load_collection logs success message."""
    from pathlib import Path

    mock_db_client = Mock()
    commands = CLICommands(mock_db_client)

    mock_expanduser.return_value = "/expanded/path"
    mock_exists.return_value = True
    mock_validate_path.return_value = Path("/expanded/path")
    commands.collection_service.load_collection = Mock()

    with caplog.at_level("INFO"):
        commands.load_collection("test-collection", "~/path/to/adrs")

    assert (
        "Successfully loaded ADRs from /expanded/path into collection 'test-collection'"
        in caplog.text
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


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_create_command(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function routes create command correctly."""
    from src.cli.main import main

    # Setup mocks
    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands

    # Return a JSON-serializable dictionary
    mock_result = {"result": {"name": "test-collection"}}
    mock_commands.create_collection.return_value = mock_result

    # Mock sys.argv
    with patch("sys.argv", ["vdb-flow", "create", "test-collection"]):
        main()

    # Verify database was initialized and create_collection was called with defaults
    mock_get_commands.assert_called_once()
    mock_commands.create_collection.assert_called_once_with(
        "test-collection", "Cosine", enable_hybrid=True, vector_size=None
    )
    # Verify output formatting was called (default is json)
    mock_format_output.assert_called_once_with(mock_result, "json", "create")
    mock_log_summary.assert_called_once_with(
        mock_result, "create", {"collection": "test-collection"}
    )


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_create_command_with_options(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function routes create command with all options."""
    from src.cli.main import main

    # Setup mocks
    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands

    # Return a JSON-serializable dictionary
    mock_result = {"result": {"name": "test-collection"}}
    mock_commands.create_collection.return_value = mock_result

    # Mock sys.argv with all options
    with patch(
        "sys.argv",
        [
            "vdb-flow",
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
    mock_get_commands.assert_called_once()
    mock_commands.create_collection.assert_called_once_with(
        "test-collection", "Euclid", enable_hybrid=False, vector_size=1024
    )
    # Verify output formatting was called (default is json)
    mock_format_output.assert_called_once_with(mock_result, "json", "create")
    mock_log_summary.assert_called_once_with(
        mock_result, "create", {"collection": "test-collection"}
    )


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_delete_command(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function routes delete command."""
    from src.cli.main import main

    # Setup mocks
    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands

    # Return a JSON-serializable dictionary
    mock_result = {"status": "ok", "collection": "test-collection"}
    mock_commands.delete_collection.return_value = mock_result

    # Mock sys.argv
    with patch("sys.argv", ["vdb-flow", "delete", "test-collection"]):
        main()

    mock_get_commands.assert_called_once()
    mock_commands.delete_collection.assert_called_once_with("test-collection")
    # Verify output formatting was called (default is json)
    mock_format_output.assert_called_once_with(mock_result, "json", "delete")
    mock_log_summary.assert_called_once_with(
        mock_result, "delete", {"collection": "test-collection"}
    )


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_list_command(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function routes list command."""
    from src.cli.main import main

    # Setup mocks
    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands

    # Return a JSON-serializable list
    mock_result = [{"name": "collection1"}, {"name": "collection2"}]
    mock_commands.list_collections.return_value = mock_result

    # Mock sys.argv
    with patch("sys.argv", ["vdb-flow", "list"]):
        main()

    mock_get_commands.assert_called_once()
    mock_commands.list_collections.assert_called_once()
    # Verify output formatting was called (default is json)
    mock_format_output.assert_called_once_with(mock_result, "json", "list")
    mock_log_summary.assert_called_once_with(mock_result, "list", None)


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_info_command(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function routes info command."""
    from src.cli.main import main

    # Setup mocks
    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands

    # Return a JSON-serializable dictionary
    mock_result = {"result": {"name": "test-collection", "points_count": 100}}
    mock_commands.get_collection_info.return_value = mock_result

    # Mock sys.argv
    with patch("sys.argv", ["vdb-flow", "info", "test-collection"]):
        main()

    mock_get_commands.assert_called_once()
    mock_commands.get_collection_info.assert_called_once_with("test-collection")
    # Verify output formatting was called (default is json)
    mock_format_output.assert_called_once_with(mock_result, "json", "info")
    mock_log_summary.assert_called_once_with(
        mock_result, "info", {"collection": "test-collection"}
    )


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
@patch("src.cli.commands.os.path.exists")
@patch("src.cli.commands.os.path.expanduser")
def test_main_load_command(
    mock_expanduser,
    mock_exists,
    mock_setup_logging,
    mock_log_summary,
    mock_format_output,
    mock_get_commands,
):
    """Test main function routes load command."""
    from src.cli.main import main

    # Setup mocks
    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands

    # Mock path expansion and existence
    mock_expanduser.return_value = "/path/to/adrs"
    mock_exists.return_value = True

    # Return a JSON-serializable dictionary
    mock_result = {
        "status": "ok",
        "collection": "test-collection",
        "path": "/path/to/adrs",
        "runtime_seconds": 10.5,
        "runtime_formatted": "0m 10.5s",
    }
    mock_commands.load_collection.return_value = mock_result

    # Mock sys.argv
    with patch("sys.argv", ["vdb-flow", "load", "test-collection", "/path/to/adrs"]):
        main()

    mock_get_commands.assert_called_once()
    mock_commands.load_collection.assert_called_once_with(
        "test-collection", "/path/to/adrs"
    )
    # Verify output formatting was called (default is json)
    mock_format_output.assert_called_once_with(mock_result, "json", "load")
    mock_log_summary.assert_called_once_with(mock_result, "load", None)


@patch("src.cli.main.sys.exit")
def test_main_invalid_command(mock_exit):
    """Test main function handles invalid command without initializing database."""
    from src.cli.main import main

    # Mock sys.argv with invalid command
    with patch("sys.argv", ["vdb-flow", "invalid-command"]):
        try:
            main()
        except SystemExit:
            pass  # argparse raises SystemExit, which we're mocking

    # argparse calls sys.exit(2) for invalid arguments, and may call it multiple times
    # Just verify it was called (at least once)
    # Also verify database was NOT initialized (no need to mock _get_commands)
    assert mock_exit.called


def test_version_command():
    """Test version command parsing."""
    parser = create_parser()

    args = parser.parse_args(["version"])
    assert args.action == "version"


@patch("src.cli.main._show_version")
def test_main_version_command(mock_show_version):
    """Test main function routes version command without initializing database."""
    from src.cli.main import main

    # Mock sys.argv
    with patch("sys.argv", ["vdb-flow", "version"]):
        main()

    # Verify version was shown
    mock_show_version.assert_called_once()

    # Verify database was NOT initialized (no calls to get_config or create_vector_database)
    # This is verified by the fact that we don't need to mock them


# Tests for output formatting functionality


def test_format_list_table_empty():
    """Test _format_list_table with empty list."""
    result = _format_list_table([])
    assert result == "No collections found."


def test_format_list_table_single_collection():
    """Test _format_list_table with single collection."""
    collections = [{"name": "test-collection", "points_count": 100, "status": "active"}]
    result = _format_list_table(collections)
    assert "Name" in result
    assert "Vectors" in result
    assert "Status" in result
    assert "test-collection" in result
    assert "100" in result
    assert "active" in result


def test_format_list_table_multiple_collections():
    """Test _format_list_table with multiple collections."""
    collections = [
        {"name": "collection1", "points_count": 100, "status": "active"},
        {"name": "collection2", "vectors_count": 200, "status": "active"},
        {"name": "collection3", "indexed_vectors_count": 300},
    ]
    result = _format_list_table(collections)
    assert "collection1" in result
    assert "collection2" in result
    assert "collection3" in result
    assert "100" in result
    assert "200" in result
    assert "300" in result


def test_format_list_table_zero_points_count():
    """Test _format_list_table correctly handles zero points_count."""
    # This tests the bug fix: 0 should be displayed, not fall through to other fields
    collections = [
        {"name": "empty-collection", "points_count": 0, "indexed_vectors_count": 123}
    ]
    result = _format_list_table(collections)
    assert "empty-collection" in result
    # Should show 0 (points_count), not 123 (indexed_vectors_count)
    # Find the line with empty-collection and verify it shows 0
    lines = result.split("\n")
    for line in lines:
        if "empty-collection" in line:
            # The line should contain 0 in the Vectors column
            assert "0" in line
            # Should NOT contain 123 in the same line
            assert "123" not in line
            break


def test_format_list_table_missing_fields():
    """Test _format_list_table handles missing fields gracefully."""
    collections = [{"name": "collection1"}]
    result = _format_list_table(collections)
    assert "collection1" in result
    assert "0" in result  # Default for missing count
    assert "active" in result  # Default status


def test_format_dict_table_empty():
    """Test _format_dict_table with empty dict."""
    result = _format_dict_table({})
    assert result == "No data available."


def test_format_dict_table_simple_dict():
    """Test _format_dict_table with simple dictionary."""
    data = {"name": "test-collection", "points_count": 100}
    result = _format_dict_table(data)
    assert "Key" in result
    assert "Value" in result
    assert "name" in result
    assert "test-collection" in result
    assert "points_count" in result
    assert "100" in result


def test_format_dict_table_nested_dict():
    """Test _format_dict_table with nested dictionary."""
    data = {
        "status": "ok",
        "result": {"name": "test-collection", "points_count": 100},
    }
    result = _format_dict_table(data)
    assert "status" in result
    assert "result.name" in result
    assert "result.points_count" in result
    assert "test-collection" in result
    assert "100" in result


def test_format_dict_table_with_list():
    """Test _format_dict_table handles lists in dict."""
    data = {"name": "test", "items": [1, 2, 3]}
    result = _format_dict_table(data)
    assert "name" in result
    assert "items" in result
    assert "[3 items]" in result


@patch("src.cli.main.print")
def test_format_output_json_list(mock_print):
    """Test _format_output with json format for list."""
    data = [{"name": "collection1"}]
    _format_output(data, "json", "list")
    mock_print.assert_called_once()
    # Verify it printed JSON (check the call args)
    call_args = mock_print.call_args[0][0]
    assert "collection1" in call_args


@patch("src.cli.main.print")
def test_format_output_table_list(mock_print):
    """Test _format_output with table format for list command."""
    data = [{"name": "collection1", "points_count": 100}]
    _format_output(data, "table", "list")
    mock_print.assert_called_once()
    call_args = mock_print.call_args[0][0]
    assert "Name" in call_args
    assert "collection1" in call_args


@patch("src.cli.main.print")
def test_format_output_table_dict(mock_print):
    """Test _format_output with table format for dict."""
    data = {"name": "test-collection", "points_count": 100}
    _format_output(data, "table", "info")
    mock_print.assert_called_once()
    call_args = mock_print.call_args[0][0]
    assert "Key" in call_args
    assert "name" in call_args


@patch("src.cli.main.print")
def test_format_output_json_dict(mock_print):
    """Test _format_output with json format for dict."""
    data = {"name": "test-collection", "points_count": 100}
    _format_output(data, "json", "info")
    mock_print.assert_called_once()
    call_args = mock_print.call_args[0][0]
    assert "test-collection" in call_args


@patch("src.cli.main.logger")
def test_log_summary_list(mock_logger):
    """Test _log_summary logs for list command."""
    data = [{"name": "collection1"}, {"name": "collection2"}]
    _log_summary(data, "list")
    mock_logger.info.assert_called_once_with("Found 2 collection(s)")


@patch("src.cli.main.logger")
def test_log_summary_create(mock_logger):
    """Test _log_summary logs for create command."""
    data = {"result": {"name": "test-collection"}}
    _log_summary(data, "create")
    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0][0]
    assert "Collection created" in call_args
    assert "test-collection" in call_args


@patch("src.cli.main.logger")
def test_log_summary_delete(mock_logger):
    """Test _log_summary logs for delete command."""
    data = {"status": "ok", "collection": "test-collection"}
    _log_summary(data, "delete")
    mock_logger.info.assert_called_once_with("Collection deleted: name=test-collection")


@patch("src.cli.main.logger")
def test_log_summary_info(mock_logger):
    """Test _log_summary logs for info command."""
    data = {"result": {"name": "test-collection", "points_count": 100}}
    _log_summary(data, "info")
    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0][0]
    assert "Collection info" in call_args
    assert "test-collection" in call_args
    assert "vectors=100" in call_args


@patch("src.cli.main.logger")
def test_log_summary_clear(mock_logger):
    """Test _log_summary logs for clear command."""
    data = {"status": "ok", "collection": "test-collection"}
    _log_summary(data, "clear")
    mock_logger.info.assert_called_once_with("Collection cleared: name=test-collection")


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_list_command_with_output_table(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function uses table output when --output table is specified."""
    from src.cli.main import main

    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands
    mock_result = [{"name": "collection1"}, {"name": "collection2"}]
    mock_commands.list_collections.return_value = mock_result

    with patch("sys.argv", ["vdb-flow", "list", "--output", "table"]):
        main()

    mock_commands.list_collections.assert_called_once()
    mock_format_output.assert_called_once_with(mock_result, "table", "list")
    mock_log_summary.assert_called_once_with(mock_result, "list", None)


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_list_command_with_output_json(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function uses json output when --output json is specified."""
    from src.cli.main import main

    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands
    mock_result = [{"name": "collection1"}]
    mock_commands.list_collections.return_value = mock_result

    with patch("sys.argv", ["vdb-flow", "list", "--output", "json"]):
        main()

    mock_commands.list_collections.assert_called_once()
    mock_format_output.assert_called_once_with(mock_result, "json", "list")
    mock_log_summary.assert_called_once_with(mock_result, "list", None)


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_list_command_default_output_json(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function defaults to json output when --output is not specified."""
    from src.cli.main import main

    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands
    mock_result = [{"name": "collection1"}]
    mock_commands.list_collections.return_value = mock_result

    with patch("sys.argv", ["vdb-flow", "list"]):
        main()

    mock_commands.list_collections.assert_called_once()
    # Default should be json
    mock_format_output.assert_called_once_with(mock_result, "json", "list")
    mock_log_summary.assert_called_once_with(mock_result, "list", None)


@patch("src.cli.main._get_commands")
@patch("src.cli.main._format_output")
@patch("src.cli.main._log_summary")
@patch("src.cli.main.setup_logging")
def test_main_create_command_with_output_table(
    mock_setup_logging, mock_log_summary, mock_format_output, mock_get_commands
):
    """Test main function uses table output for create command."""
    from src.cli.main import main

    mock_commands = Mock()
    mock_get_commands.return_value = mock_commands
    mock_result = {"result": {"name": "test-collection"}}
    mock_commands.create_collection.return_value = mock_result

    with patch(
        "sys.argv", ["vdb-flow", "create", "test-collection", "--output", "table"]
    ):
        main()

    mock_format_output.assert_called_once_with(mock_result, "table", "create")
    mock_log_summary.assert_called_once_with(
        mock_result, "create", {"collection": "test-collection"}
    )
