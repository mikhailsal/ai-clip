"""Tests for the clipboard module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ai_clip.clipboard import (
    ClipboardError,
    _detect_session_type,
    _run,
    read_clipboard,
    read_primary_selection,
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


class TestReadPrimarySelection:
    def test_x11(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard._run", return_value="primary text") as mock,
        ):
            result = read_primary_selection()
            assert result == "primary text"
            mock.assert_called_once_with(["xclip", "-selection", "primary", "-o"])

    def test_wayland(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard._run", return_value="wayland primary\n") as mock,
        ):
            result = read_primary_selection()
            assert result == "wayland primary"
            mock.assert_called_once_with(["wl-paste", "--primary", "--no-newline"])


class TestWriteClipboard:
    def test_x11(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard.subprocess.Popen", return_value=mock_proc) as mock_popen,
        ):
            write_clipboard("hello")
            mock_popen.assert_called_once_with(
                ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE
            )
            mock_proc.communicate.assert_called_once_with(input=b"hello", timeout=5)

    def test_wayland(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard.subprocess.Popen", return_value=mock_proc) as mock_popen,
        ):
            write_clipboard("hello")
            mock_popen.assert_called_once_with(["wl-copy"], stdin=subprocess.PIPE)

    def test_command_not_found(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard.subprocess.Popen", side_effect=FileNotFoundError),
            pytest.raises(ClipboardError, match="Command not found"),
        ):
            write_clipboard("hello")

    def test_timeout(self):
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="xclip", timeout=5)
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard.subprocess.Popen", return_value=mock_proc),
            pytest.raises(ClipboardError, match="timed out"),
        ):
            write_clipboard("hello")
        mock_proc.kill.assert_called_once()

    def test_nonzero_return(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard.subprocess.Popen", return_value=mock_proc),
            pytest.raises(ClipboardError, match="failed"),
        ):
            write_clipboard("hello")


class TestSimulateCopy:
    def test_x11(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_copy()
            mock_run.assert_called_once_with(["xdotool", "key", "--delay", "50", "ctrl+c"])
            mock_sleep.assert_called_once_with(0.3)

    def test_wayland(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_copy()
            mock_run.assert_called_once_with(["ydotool", "key", "29:1", "46:1", "46:0", "29:0"])
            mock_sleep.assert_called_once_with(0.3)


class TestSimulatePaste:
    def test_x11(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="x11"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_paste()
            mock_run.assert_called_once_with(["xdotool", "key", "--delay", "50", "ctrl+v"])
            mock_sleep.assert_called_once_with(0.3)

    def test_wayland(self):
        with (
            patch("ai_clip.clipboard._detect_session_type", return_value="wayland"),
            patch("ai_clip.clipboard._run") as mock_run,
            patch("ai_clip.clipboard.time.sleep") as mock_sleep,
        ):
            simulate_paste()
            mock_run.assert_called_once_with(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])
            mock_sleep.assert_called_once_with(0.3)
