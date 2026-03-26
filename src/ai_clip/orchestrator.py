"""Main orchestration flow for ai-clip.

Coordinates: clipboard capture -> command selection -> AI transformation -> paste back.
"""

from __future__ import annotations

import logging
import time
import typing

if typing.TYPE_CHECKING:
    from pathlib import Path

from ai_clip.ai_client import AIClientError, transform_text
from ai_clip.clipboard import (
    COPY_RETRIES,
    COPY_RETRY_DELAY,
    ClipboardError,
    read_clipboard,
    simulate_copy,
    simulate_paste,
    write_clipboard,
)
from ai_clip.config import AppConfig, load_config
from ai_clip.history import build_command_list, load_history
from ai_clip.picker import PickerResult, show_picker
from ai_clip.sound import play_sound

logger = logging.getLogger(__name__)

_TRUNCATE_LEN = 200


class _PerfTimer:
    """Lightweight timer for tracking phase-by-phase latency in a pipeline."""

    __slots__ = ("_t0", "_last", "_name")

    def __init__(self, name: str):
        self._name = name
        self._t0 = time.monotonic()
        self._last = self._t0

    def phase(self, label: str) -> float:
        """Log time since last phase and since start. Returns phase duration in ms."""
        now = time.monotonic()
        phase_ms = (now - self._last) * 1000
        total_ms = (now - self._t0) * 1000
        logger.info(
            "[PERF %s] %s: %.0fms (total %.0fms)",
            self._name,
            label,
            phase_ms,
            total_ms,
        )
        self._last = now
        return phase_ms

    def total_ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000


def _truncate(text: str) -> str:
    """Truncate text for log display, appending '...' if shortened."""
    if len(text) <= _TRUNCATE_LEN:
        return repr(text)
    return repr(text[:_TRUNCATE_LEN]) + f"... ({len(text)} chars total)"


def _capture_selected_text(source_window: str | None = None) -> tuple[str, str]:
    """Capture the currently selected text using Ctrl+C.

    Saves old clipboard, simulates Ctrl+C targeting the source window,
    then reads back. If the clipboard changed, returns immediately.
    If unchanged but non-empty, trusts the first attempt after a single
    short retry (the text might genuinely be the same as what was on the
    clipboard). Only does full retries when clipboard is truly empty.

    Args:
        source_window: X11 window ID captured at program start, before focus shifts.

    Returns (text, capture_method).
    """
    old_clipboard = _safe_read_clipboard()

    simulate_copy(source_window)
    text = read_clipboard()

    if text.strip() and text != old_clipboard:
        logger.debug("Captured text via Ctrl+C (clipboard changed)")
        return text, "ctrl_c"

    if text.strip():
        logger.debug("Clipboard unchanged after Ctrl+C, but has content — accepting it")
        return text, "ctrl_c_unchanged"

    for attempt in range(1, COPY_RETRIES):
        logger.debug("Clipboard empty after Ctrl+C, retrying (attempt %d)", attempt + 1)
        time.sleep(COPY_RETRY_DELAY)
        simulate_copy(source_window)
        text = read_clipboard()
        if text.strip():
            logger.debug("Captured text via Ctrl+C retry (attempt %d)", attempt + 1)
            return text, "ctrl_c"

    return "", "ctrl_c_empty"


def _safe_read_clipboard() -> str:
    """Read clipboard, returning empty string on any error."""
    try:
        return read_clipboard()
    except ClipboardError:
        return ""


def _find_prompt_for_command(label: str, config: AppConfig) -> tuple[str, str | None]:
    """Find the prompt and optional model override for a command label.

    Returns (prompt, model_override). For pinned commands, uses their
    configured prompt and model. For history/custom commands, the label
    itself is the prompt.
    """
    for pinned in config.pinned_commands:
        if pinned.label == label:
            return pinned.prompt, pinned.model
    return label, None


def _do_transform(
    text: str,
    command_label: str,
    config: AppConfig,
) -> str:
    """Perform the AI transformation and return the result."""
    prompt, model_override = _find_prompt_for_command(command_label, config)
    model = model_override or config.default_model

    logger.info(
        "AI request: command=%r, model=%s, prompt=%r, input=%s",
        command_label,
        model,
        prompt,
        _truncate(text),
    )

    t0 = time.monotonic()
    result = transform_text(
        text=text,
        command_prompt=prompt,
        api_key=config.openrouter_api_key,
        model=model,
        timeout=config.timeout_seconds,
    )
    elapsed_ms = (time.monotonic() - t0) * 1000

    logger.info(
        "AI response: elapsed=%.0fms, output=%s",
        elapsed_ms,
        _truncate(result),
    )
    return result


def run_with_picker(config_path: Path | None = None, source_window: str | None = None) -> bool:
    """Full interactive flow: copy -> pick command -> AI -> paste.

    Returns True on success, False on cancellation or error.
    """
    perf = _PerfTimer("picker")
    logger.info("=== run_with_picker: starting picker flow ===")
    config = load_config(config_path)
    history = load_history()
    commands = build_command_list(config.pinned_commands, history)
    perf.phase("config+history")

    try:
        original_text, capture_method = _capture_selected_text(source_window)
    except ClipboardError as exc:
        logger.error("Failed to read clipboard: %s", exc)
        return False
    perf.phase("capture_text")

    if not original_text.strip():
        logger.warning("Clipboard is empty, nothing to transform")
        return False

    logger.debug(
        "Captured text: method=%s, length=%d, text=%s",
        capture_method,
        len(original_text),
        _truncate(original_text),
    )

    picker_result: PickerResult = show_picker(commands)
    if picker_result.cancelled or not picker_result.command:
        logger.info("User cancelled the picker")
        return False
    perf.phase("picker_ui")

    logger.info(
        "Picker result: command=%r, trigger=%s",
        picker_result.command,
        picker_result.trigger or "unknown",
    )

    logger.debug("Execute transform: trigger=%s", picker_result.trigger or "unknown")
    return _execute_transform(
        original_text,
        picker_result.command,
        config,
        history,
        source_window=source_window,
        perf=perf,
    )


def run_direct_command(
    command_label: str, config_path: Path | None = None, source_window: str | None = None
) -> bool:
    """Direct command execution without picker (for dedicated hotkeys).

    Returns True on success, False on error.
    """
    perf = _PerfTimer("direct")
    logger.info("=== run_direct_command: command=%r (dedicated hotkey) ===", command_label)
    config = load_config(config_path)
    history = load_history()
    perf.phase("config+history")

    try:
        original_text, capture_method = _capture_selected_text(source_window)
    except ClipboardError as exc:
        logger.error("Failed to read clipboard: %s", exc)
        return False
    perf.phase("capture_text")

    if not original_text.strip():
        logger.warning("Clipboard is empty, nothing to transform")
        return False

    logger.debug(
        "Captured text: method=%s, length=%d, text=%s",
        capture_method,
        len(original_text),
        _truncate(original_text),
    )

    logger.debug("Execute transform: trigger=direct_hotkey")
    return _execute_transform(
        original_text,
        command_label,
        config,
        history,
        source_window=source_window,
        perf=perf,
    )


def _execute_transform(
    text: str,
    command_label: str,
    config: AppConfig,
    history,
    source_window: str | None = None,
    perf: _PerfTimer | None = None,
) -> bool:
    """Transform text and paste the result. Updates history on success."""

    if config.sound_enabled:
        play_sound(config.sound_acknowledge)

    try:
        result = _do_transform(text, command_label, config)
    except AIClientError as exc:
        logger.error("AI transformation failed: %s", exc)
        return False
    if perf:
        perf.phase("ai_transform")

    try:
        write_clipboard(result)
        if perf:
            perf.phase("write_clipboard")
        simulate_paste(source_window)
        if perf:
            perf.phase("simulate_paste")
    except ClipboardError as exc:
        logger.error("Failed to paste result: %s", exc)
        return False

    history.record_usage(command_label)
    history.save()
    if perf:
        perf.phase("history_save")
        epoch_end = int(time.time() * 1000)
        logger.info(
            "Transformation complete: command=%r, total=%.0fms, epoch_end_ms=%d",
            command_label,
            perf.total_ms(),
            epoch_end,
        )
    else:
        logger.info("Transformation complete: command=%r, pasted result", command_label)
    return True
