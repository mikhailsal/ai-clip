"""Clipboard operations: read, write, simulate copy/paste.

Supports both X11 (xclip, xdotool) and Wayland (wl-copy, wl-paste, ydotool).
"""

import logging
import subprocess
import time

logger = logging.getLogger(__name__)

COPY_PASTE_DELAY = 0.15
XDOTOOL_KEY_DELAY = 50


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


def write_clipboard(text: str) -> None:
    """Write text to system clipboard."""
    session = _detect_session_type()
    data = text.encode()
    if session == "wayland":
        _run(["wl-copy"], input_data=data)
    else:
        _run(["xclip", "-selection", "clipboard"], input_data=data)


def simulate_copy() -> None:
    """Simulate Ctrl+C keypress to copy selected text."""
    session = _detect_session_type()
    if session == "wayland":
        _run(["ydotool", "key", "29:1", "46:1", "46:0", "29:0"])
    else:
        _run(["xdotool", "key", "--delay", str(XDOTOOL_KEY_DELAY), "ctrl+c"])
    time.sleep(COPY_PASTE_DELAY)


def simulate_paste() -> None:
    """Simulate Ctrl+V keypress to paste clipboard."""
    session = _detect_session_type()
    if session == "wayland":
        _run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])
    else:
        _run(["xdotool", "key", "--delay", str(XDOTOOL_KEY_DELAY), "ctrl+v"])
    time.sleep(COPY_PASTE_DELAY)
