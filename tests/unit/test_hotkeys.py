"""Tests for the hotkeys module."""

from unittest.mock import MagicMock, patch

from ai_clip.config import AppConfig, PinnedCommand
from ai_clip.hotkeys import (
    _build_command_string,
    _find_next_slot,
    _get_existing_keybinding_slots,
    _run_dconf,
    _write_keybinding,
    register_hotkeys,
)


def _make_config(**overrides):
    defaults = {
        "openrouter_api_key": "sk-test",
        "default_model": "test-model",
        "main_hotkey": "<Super><Shift>a",
        "pinned_commands": [
            PinnedCommand(
                label="Translate",
                prompt="Translate",
                dedicated_hotkey="<Super><Shift>e",
            ),
            PinnedCommand(label="Fix", prompt="Fix grammar"),
        ],
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


class TestRunDconf:
    def test_success(self):
        with patch("ai_clip.hotkeys.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")
            result = _run_dconf(["read", "/some/path"])
        assert result == "output"
        mock_run.assert_called_once()

    def test_failure_returns_empty(self):
        with patch("ai_clip.hotkeys.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
            result = _run_dconf(["read", "/bad/path"])
        assert result == ""


class TestGetExistingKeybindingSlots:
    def test_parses_slots(self):
        base = "/org/cinnamon/desktop/keybindings/custom-keybindings"
        raw = f"['{base}/custom0/', '{base}/custom1/']"
        with patch("ai_clip.hotkeys._run_dconf", return_value=raw):
            result = _get_existing_keybinding_slots()
        assert len(result) == 2

    def test_empty(self):
        with patch("ai_clip.hotkeys._run_dconf", return_value=""):
            result = _get_existing_keybinding_slots()
        assert result == []

    def test_invalid_json(self):
        with patch("ai_clip.hotkeys._run_dconf", return_value="not json"):
            result = _get_existing_keybinding_slots()
        assert result == []


class TestFindNextSlot:
    def test_empty(self):
        assert _find_next_slot([]) == 0

    def test_with_existing(self):
        existing = [
            "/org/cinnamon/desktop/keybindings/custom-keybindings/custom0/",
            "/org/cinnamon/desktop/keybindings/custom-keybindings/custom1/",
        ]
        assert _find_next_slot(existing) == 2

    def test_with_gap(self):
        existing = [
            "/org/cinnamon/desktop/keybindings/custom-keybindings/custom0/",
            "/org/cinnamon/desktop/keybindings/custom-keybindings/custom2/",
        ]
        assert _find_next_slot(existing) == 1


class TestWriteKeybinding:
    def test_writes_three_keys(self):
        with patch("ai_clip.hotkeys._run_dconf") as mock_dconf:
            _write_keybinding(5, "test", "echo hello", "<Super>t")
        assert mock_dconf.call_count == 3


class TestBuildCommandString:
    def test_without_args(self):
        result = _build_command_string()
        assert "python" in result
        assert "-m ai_clip" in result

    def test_with_args(self):
        result = _build_command_string('--command "Fix"')
        assert '--command "Fix"' in result


class TestRegisterHotkeys:
    def test_registers_main_and_pinned(self, capsys):
        config = _make_config()
        with (
            patch("ai_clip.hotkeys._get_existing_keybinding_slots", return_value=[]),
            patch("ai_clip.hotkeys._write_keybinding") as mock_write,
            patch("ai_clip.hotkeys._run_dconf"),
        ):
            register_hotkeys(config)

        assert mock_write.call_count == 2
        output = capsys.readouterr().out
        assert "2 hotkey(s)" in output

    def test_skips_pinned_without_hotkey(self, capsys):
        config = _make_config(pinned_commands=[PinnedCommand(label="No hotkey", prompt="P")])
        with (
            patch("ai_clip.hotkeys._get_existing_keybinding_slots", return_value=[]),
            patch("ai_clip.hotkeys._write_keybinding") as mock_write,
            patch("ai_clip.hotkeys._run_dconf"),
        ):
            register_hotkeys(config)
        assert mock_write.call_count == 1

    def test_appends_to_existing_slots(self):
        config = _make_config(pinned_commands=[])
        existing = ["/org/cinnamon/desktop/keybindings/custom-keybindings/custom0/"]
        with (
            patch("ai_clip.hotkeys._get_existing_keybinding_slots", return_value=existing),
            patch("ai_clip.hotkeys._write_keybinding"),
            patch("ai_clip.hotkeys._run_dconf") as mock_dconf,
        ):
            register_hotkeys(config)
        final_call = mock_dconf.call_args_list[-1]
        assert "custom0" in str(final_call)
        assert "custom1" in str(final_call)
