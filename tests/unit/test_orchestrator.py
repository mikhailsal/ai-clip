"""Tests for the orchestrator module."""

from unittest.mock import MagicMock, patch

from ai_clip.ai_client import AIClientError
from ai_clip.clipboard import ClipboardError
from ai_clip.config import AppConfig, PinnedCommand
from ai_clip.orchestrator import (
    _capture_selected_text,
    _do_transform,
    _execute_transform,
    _find_prompt_for_command,
    _truncate,
    run_direct_command,
    run_with_picker,
)
from ai_clip.picker import PickerResult


def _make_config(**overrides):
    defaults = {
        "openrouter_api_key": "sk-test",
        "default_model": "test-model",
        "timeout_seconds": 10,
        "pinned_commands": [
            PinnedCommand(label="Translate", prompt="Translate to EN", model="gpt-4"),
            PinnedCommand(label="Fix", prompt="Fix grammar"),
        ],
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


class TestTruncate:
    def test_short_text(self):
        assert _truncate("hello") == "'hello'"

    def test_long_text(self):
        text = "x" * 300
        result = _truncate(text)
        assert "... (300 chars total)" in result
        assert result.startswith("'")


class TestCaptureSelectedText:
    def test_uses_primary_selection(self):
        with patch("ai_clip.orchestrator.read_primary_selection", return_value="selected"):
            text, method = _capture_selected_text()
        assert text == "selected"
        assert method == "primary_selection"

    def test_falls_back_to_ctrl_c(self):
        with (
            patch("ai_clip.orchestrator.read_primary_selection", return_value=""),
            patch("ai_clip.orchestrator.simulate_copy"),
            patch("ai_clip.orchestrator.read_clipboard", return_value="copied"),
        ):
            text, method = _capture_selected_text()
        assert text == "copied"
        assert method == "ctrl_c"

    def test_falls_back_on_primary_error(self):
        with (
            patch(
                "ai_clip.orchestrator.read_primary_selection",
                side_effect=ClipboardError("fail"),
            ),
            patch("ai_clip.orchestrator.simulate_copy"),
            patch("ai_clip.orchestrator.read_clipboard", return_value="copied"),
        ):
            text, method = _capture_selected_text()
        assert text == "copied"
        assert method == "ctrl_c"


class TestFindPromptForCommand:
    def test_pinned_command(self):
        config = _make_config()
        prompt, model = _find_prompt_for_command("Translate", config)
        assert prompt == "Translate to EN"
        assert model == "gpt-4"

    def test_pinned_without_model(self):
        config = _make_config()
        prompt, model = _find_prompt_for_command("Fix", config)
        assert prompt == "Fix grammar"
        assert model is None

    def test_custom_command(self):
        config = _make_config()
        prompt, model = _find_prompt_for_command("Make it funny", config)
        assert prompt == "Make it funny"
        assert model is None


class TestDoTransform:
    def test_uses_pinned_model(self):
        config = _make_config()
        with patch("ai_clip.orchestrator.transform_text", return_value="done") as mock:
            result = _do_transform("text", "Translate", config)
        assert result == "done"
        mock.assert_called_once_with(
            text="text",
            command_prompt="Translate to EN",
            api_key="sk-test",
            model="gpt-4",
            timeout=10,
        )

    def test_uses_default_model_for_custom(self):
        config = _make_config()
        with patch("ai_clip.orchestrator.transform_text", return_value="done") as mock:
            _do_transform("text", "Custom cmd", config)
        assert mock.call_args[1]["model"] == "test-model"

    def test_uses_default_when_pinned_has_no_model(self):
        config = _make_config()
        with patch("ai_clip.orchestrator.transform_text", return_value="done") as mock:
            _do_transform("text", "Fix", config)
        assert mock.call_args[1]["model"] == "test-model"


class TestExecuteTransform:
    def test_success(self):
        config = _make_config()
        history = MagicMock()
        with (
            patch("ai_clip.orchestrator._do_transform", return_value="result"),
            patch("ai_clip.orchestrator.write_clipboard") as mock_write,
            patch("ai_clip.orchestrator.simulate_paste") as mock_paste,
        ):
            result = _execute_transform("text", "Fix", config, history)
        assert result is True
        mock_write.assert_called_once_with("result")
        mock_paste.assert_called_once()
        history.record_usage.assert_called_once_with("Fix")
        history.save.assert_called_once()

    def test_ai_error(self):
        config = _make_config()
        history = MagicMock()
        with patch("ai_clip.orchestrator._do_transform", side_effect=AIClientError("fail")):
            result = _execute_transform("text", "Fix", config, history)
        assert result is False
        history.record_usage.assert_not_called()

    def test_paste_error(self):
        config = _make_config()
        history = MagicMock()
        with (
            patch("ai_clip.orchestrator._do_transform", return_value="result"),
            patch("ai_clip.orchestrator.write_clipboard", side_effect=ClipboardError("fail")),
        ):
            result = _execute_transform("text", "Fix", config, history)
        assert result is False


class TestRunWithPicker:
    def test_success(self, tmp_path):
        config_path = tmp_path / "config.toml"
        with (
            patch("ai_clip.orchestrator.load_config", return_value=_make_config()),
            patch("ai_clip.orchestrator.load_history", return_value=MagicMock()),
            patch("ai_clip.orchestrator.build_command_list", return_value=[]),
            patch(
                "ai_clip.orchestrator._capture_selected_text",
                return_value=("hello", "primary_selection"),
            ),
            patch(
                "ai_clip.orchestrator.show_picker",
                return_value=PickerResult(command="Fix", trigger="ctrl_2"),
            ),
            patch("ai_clip.orchestrator._execute_transform", return_value=True) as mock_exec,
        ):
            result = run_with_picker(config_path)
        assert result is True
        mock_exec.assert_called_once()

    def test_clipboard_error(self, tmp_path):
        with (
            patch("ai_clip.orchestrator.load_config", return_value=_make_config()),
            patch("ai_clip.orchestrator.load_history", return_value=MagicMock()),
            patch("ai_clip.orchestrator.build_command_list", return_value=[]),
            patch(
                "ai_clip.orchestrator._capture_selected_text",
                side_effect=ClipboardError("fail"),
            ),
        ):
            result = run_with_picker(tmp_path / "c.toml")
        assert result is False

    def test_empty_clipboard(self, tmp_path):
        with (
            patch("ai_clip.orchestrator.load_config", return_value=_make_config()),
            patch("ai_clip.orchestrator.load_history", return_value=MagicMock()),
            patch("ai_clip.orchestrator.build_command_list", return_value=[]),
            patch(
                "ai_clip.orchestrator._capture_selected_text",
                return_value=("  ", "primary_selection"),
            ),
        ):
            result = run_with_picker(tmp_path / "c.toml")
        assert result is False

    def test_cancelled_picker(self, tmp_path):
        with (
            patch("ai_clip.orchestrator.load_config", return_value=_make_config()),
            patch("ai_clip.orchestrator.load_history", return_value=MagicMock()),
            patch("ai_clip.orchestrator.build_command_list", return_value=[]),
            patch(
                "ai_clip.orchestrator._capture_selected_text",
                return_value=("hello", "primary_selection"),
            ),
            patch(
                "ai_clip.orchestrator.show_picker",
                return_value=PickerResult(command="", cancelled=True),
            ),
        ):
            result = run_with_picker(tmp_path / "c.toml")
        assert result is False


class TestRunDirectCommand:
    def test_success(self, tmp_path):
        with (
            patch("ai_clip.orchestrator.load_config", return_value=_make_config()),
            patch("ai_clip.orchestrator.load_history", return_value=MagicMock()),
            patch(
                "ai_clip.orchestrator._capture_selected_text",
                return_value=("hello", "primary_selection"),
            ),
            patch("ai_clip.orchestrator._execute_transform", return_value=True) as mock_exec,
        ):
            result = run_direct_command("Translate", tmp_path / "c.toml")
        assert result is True
        mock_exec.assert_called_once()

    def test_clipboard_error(self, tmp_path):
        with (
            patch("ai_clip.orchestrator.load_config", return_value=_make_config()),
            patch("ai_clip.orchestrator.load_history", return_value=MagicMock()),
            patch(
                "ai_clip.orchestrator._capture_selected_text",
                side_effect=ClipboardError("fail"),
            ),
        ):
            result = run_direct_command("Translate", tmp_path / "c.toml")
        assert result is False

    def test_empty_clipboard(self, tmp_path):
        with (
            patch("ai_clip.orchestrator.load_config", return_value=_make_config()),
            patch("ai_clip.orchestrator.load_history", return_value=MagicMock()),
            patch(
                "ai_clip.orchestrator._capture_selected_text",
                return_value=("", "ctrl_c"),
            ),
        ):
            result = run_direct_command("Translate", tmp_path / "c.toml")
        assert result is False
