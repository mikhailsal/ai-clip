"""Tests for the CLI module."""

from unittest.mock import MagicMock, patch

from ai_clip.cli import _list_commands, _setup_logging, build_parser, main
from ai_clip.history import CommandItem


class TestBuildParser:
    def test_default_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None
        assert args.list_commands is False
        assert args.setup_hotkeys is False
        assert args.config is None
        assert args.verbose is False

    def test_command_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--command", "Translate"])
        assert args.command == "Translate"

    def test_list_commands_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--list-commands"])
        assert args.list_commands is True

    def test_setup_hotkeys_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--setup-hotkeys"])
        assert args.setup_hotkeys is True

    def test_config_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--config", "/tmp/config.toml"])
        assert args.config == "/tmp/config.toml"

    def test_verbose_short(self):
        parser = build_parser()
        args = parser.parse_args(["-v"])
        assert args.verbose is True

    def test_verbose_long(self):
        parser = build_parser()
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True


class TestSetupLogging:
    def test_verbose(self):
        import logging

        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.NOTSET)
        _setup_logging(True)
        assert root.level == logging.DEBUG

    def test_quiet(self):
        import logging

        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.NOTSET)
        _setup_logging(False)
        assert root.level == logging.WARNING


class TestListCommands:
    def test_with_commands(self, capsys):
        items = [
            CommandItem(label="Fix", prompt="fix", is_pinned=True, count=5),
            CommandItem(label="Custom", prompt="custom", count=0),
        ]
        with (
            patch("ai_clip.cli.load_config"),
            patch("ai_clip.cli.load_history"),
            patch("ai_clip.cli.build_command_list", return_value=items),
        ):
            _list_commands(None)
        output = capsys.readouterr().out
        assert "Fix" in output
        assert "[pinned]" in output
        assert "used 5x" in output
        assert "Custom" in output

    def test_no_commands(self, capsys):
        with (
            patch("ai_clip.cli.load_config"),
            patch("ai_clip.cli.load_history"),
            patch("ai_clip.cli.build_command_list", return_value=[]),
        ):
            _list_commands(None)
        output = capsys.readouterr().out
        assert "No commands" in output


class TestSetupHotkeys:
    def test_calls_register_hotkeys(self):
        from ai_clip.cli import _setup_hotkeys

        mock_config = MagicMock()
        mock_register = MagicMock()
        with (
            patch("ai_clip.cli.load_config", return_value=mock_config),
            patch("ai_clip.hotkeys.register_hotkeys", mock_register),
        ):
            _setup_hotkeys(None)
        mock_register.assert_called_once_with(mock_config)


class TestMain:
    def test_list_commands(self):
        with patch("ai_clip.cli._list_commands") as mock:
            result = main(["--list-commands"])
        assert result == 0
        mock.assert_called_once()

    def test_setup_hotkeys(self):
        with patch("ai_clip.cli._setup_hotkeys") as mock_setup:
            result = main(["--setup-hotkeys"])
        assert result == 0
        mock_setup.assert_called_once()

    def test_direct_command_success(self):
        with patch("ai_clip.cli.run_direct_command", return_value=True):
            result = main(["--command", "Fix"])
        assert result == 0

    def test_direct_command_failure(self):
        with patch("ai_clip.cli.run_direct_command", return_value=False):
            result = main(["--command", "Fix"])
        assert result == 1

    def test_picker_success(self):
        with patch("ai_clip.cli.run_with_picker", return_value=True):
            result = main([])
        assert result == 0

    def test_picker_failure(self):
        with patch("ai_clip.cli.run_with_picker", return_value=False):
            result = main([])
        assert result == 1

    def test_verbose_flag(self):
        with (
            patch("ai_clip.cli.run_with_picker", return_value=True),
            patch("ai_clip.cli._setup_logging") as mock_log,
        ):
            main(["-v"])
        mock_log.assert_called_once_with(True)

    def test_config_path_passed(self):
        with patch("ai_clip.cli.run_with_picker", return_value=True) as mock_run:
            main(["--config", "/tmp/c.toml"])
        mock_run.assert_called_once_with("/tmp/c.toml")
