"""Clipboard operations: read, write, simulate copy/paste.

Supports both X11 (xclip, xdotool) and Wayland (wl-copy, wl-paste, ydotool).
"""

import logging
import subprocess
import time

logger = logging.getLogger(__name__)

COPY_PASTE_DELAY = 0.3
PRE_COPY_DELAY = 0.05
XDOTOOL_KEY_DELAY = 50
COPY_RETRIES = 3
COPY_RETRY_DELAY = 0.15


class ClipboardError(Exception):
    """Raised when a clipboard operation fails."""


def _detect_session_type() -> str:
    """Detect whether we are running on X11 or Wayland."""
    import os

    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session in ("x11", "wayland"):
        return session
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "x11"


def _run(cmd: list[str], input_data: bytes | None = None) -> str:
    """Run a subprocess and return stdout, raising ClipboardError on failure."""
    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            timeout=5,
        )
    except FileNotFoundError as exc:
        raise ClipboardError(f"Command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ClipboardError(f"Command timed out: {' '.join(cmd)}") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise ClipboardError(f"{cmd[0]} failed (rc={result.returncode}): {stderr}")

    return result.stdout.decode(errors="replace")


def read_clipboard() -> str:
    """Read current clipboard contents."""
    session = _detect_session_type()
    if session == "wayland":
        return _run(["wl-paste", "--no-newline"]).rstrip("\n")
    return _run(["xclip", "-selection", "clipboard", "-o"])


def read_primary_selection() -> str:
    """Read the X11 primary selection (highlighted text, no Ctrl+C needed)."""
    session = _detect_session_type()
    if session == "wayland":
        return _run(["wl-paste", "--primary", "--no-newline"]).rstrip("\n")
    return _run(["xclip", "-selection", "primary", "-o"])


def write_clipboard(text: str) -> None:
    """Write text to system clipboard.

    Uses Popen+communicate instead of subprocess.run because xclip stays
    alive to serve clipboard requests -- subprocess.run with capture_output
    causes a timeout.
    """
    session = _detect_session_type()
    data = text.encode()
    cmd = ["wl-copy"] if session == "wayland" else ["xclip", "-selection", "clipboard"]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        proc.communicate(input=data, timeout=5)
    except FileNotFoundError as exc:
        raise ClipboardError(f"Command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        raise ClipboardError(f"Command timed out: {' '.join(cmd)}") from exc
    if proc.returncode != 0:
        raise ClipboardError(f"{cmd[0]} failed (rc={proc.returncode})")


def _get_active_window_id() -> str | None:
    """Get the X11 window ID of the currently active window."""
    try:
        return _run(["xdotool", "getactivewindow"]).strip()
    except ClipboardError:
        return None


def _focus_window(window_id: str) -> None:
    """Focus an X11 window and release stuck modifier keys."""
    _run(["xdotool", "windowfocus", "--sync", window_id])
    _run(["xdotool", "keyup", "super", "ctrl", "alt", "shift"])


def simulate_copy(window_id: str | None = None) -> None:
    """Simulate Ctrl+C keypress to copy selected text.

    On X11, refocuses the source window and releases stuck modifier keys
    before sending the keypress. This works reliably across GTK, Qt, and
    Chromium apps, unlike --window which sends synthetic events that some
    toolkit ignore.
    """
    time.sleep(PRE_COPY_DELAY)
    session = _detect_session_type()
    if session == "wayland":
        _run(["ydotool", "key", "29:1", "46:1", "46:0", "29:0"])
    else:
        if window_id:
            _focus_window(window_id)
        _run(["xdotool", "key", "--delay", str(XDOTOOL_KEY_DELAY), "ctrl+c"])
    time.sleep(COPY_PASTE_DELAY)


def simulate_paste(window_id: str | None = None) -> None:
    """Simulate Ctrl+V keypress to paste clipboard."""
    session = _detect_session_type()
    if session == "wayland":
        _run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])
    else:
        if window_id:
            _focus_window(window_id)
        _run(["xdotool", "key", "--delay", str(XDOTOOL_KEY_DELAY), "ctrl+v"])
    time.sleep(COPY_PASTE_DELAY)
