"""Tests for the clipboard module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ai_clip.clipboard import (
    ClipboardError,
    _detect_session_type,
    _run,
    read_clipboard,
    simulate_copy,
    simulate_paste,
    write_clipboard,
)


class TestDetectSessionType:
    def test_x11_from_env(self):
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}, clear=False):
            assert _detect_session_type() == "x11"

    def test_wayland_from_env(self):
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}, clear=False):
            assert _detect_session_type() == "wayland"

    def test_wayland_from_display(self):
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "wayland-0"}
        with patch.dict("os.environ", env, clear=False):
            assert _detect_session_type() == "wayland"

    def test_x11_from_display(self):
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "", "DISPLAY": ":1"}
        with patch.dict("os.environ", env, clear=False):
            assert _detect_session_type() == "x11"

    def test_default_x11(self):
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict("os.environ", env, clear=False):
            assert _detect_session_type() == "x11"

    def test_unknown_session_type_ignored(self):
        env = {"XDG_SESSION_TYPE": "tty", "WAYLAND_DISPLAY": "", "DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=False):
            assert _detect_session_type() == "x11"


class TestRun:
    def test_success(self):
        with patch("ai_clip.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"hello", stderr=b"")
            assert _run(["echo", "hello"]) == "hello"

    def test_command_not_found(self):
        with (
            patch("ai_clip.clipboard.subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(ClipboardError, match="Command not found"),
        ):
            _run(["nonexistent"])

    def test_timeout(self):
        with (
            patch(
                "ai_clip.clipboard.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="test", timeout=5),
            ),
            pytest.raises(ClipboardError, match="timed out"),
        ):
            _run(["slow-cmd"])

    def test_nonzero_return(self):
        with patch("ai_clip.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"error msg")
            with pytest.raises(ClipboardError, match="error msg"):
                _run(["failing-cmd"])

    def test_passes_input_data(self):
        with patch("ai_clip.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            _run(["cmd"], input_data=b"data")
            mock_run.assert_called_once_with(["cmd"], input=b"data", capture_output=True, timeout=5)


class TestReadClipboard:
    def test_x11(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard._run", return_value="clipboard text") as mock,
        ):
            result = read_clipboard()
            assert result == "clipboard text"
            mock.assert_called_once_with(["xclip", "-selection", "clipboard", "-o"])

    def test_wayland(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard._run", return_value="wayland text\n") as mock,
        ):
            result = read_clipboard()
            assert result == "wayland text"
            mock.assert_called_once_with(["wl-paste", "--no-newline"])


class TestWriteClipboard:
    def test_x11(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard._run") as mock,
        ):
            write_clipboard("hello")
            mock.assert_called_once_with(["xclip", "-selection", "clipboard"], input_data=b"hello")

    def test_wayland(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard._run") as mock,
        ):
            write_clipboard("hello")
            mock.assert_called_once_with(["wl-copy"], input_data=b"hello")


class TestSimulateCopy:
    def test_x11(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_copy()
            mock_run.assert_called_once_with(["xdotool", "key", "--delay", "50", "ctrl+c"])
            mock_sleep.assert_called_once_with(0.15)

    def test_wayland(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_copy()
            mock_run.assert_called_once_with(["ydotool", "key", "29:1", "46:1", "46:0", "29:0"])
            mock_sleep.assert_called_once_with(0.15)


class TestSimulatePaste:
    def test_x11(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_paste()
            mock_run.assert_called_once_with(["xdotool", "key", "--delay", "50", "ctrl+v"])
            mock_sleep.assert_called_once_with(0.15)

    def test_wayland(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_paste()
            mock_run.assert_called_once_with(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])
            mock_sleep.assert_called_once_with(0.15)
