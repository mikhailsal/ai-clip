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


def _truncate(text: str) -> str:
    """Truncate text for log display, appending '...' if shortened."""
    if len(text) <= _TRUNCATE_LEN:
        return repr(text)
    return repr(text[:_TRUNCATE_LEN]) + f"... ({len(text)} chars total)"


def _capture_selected_text(source_window: str | None = None) -> tuple[str, str]:
    """Capture the currently selected text using Ctrl+C.

    Uses a robust approach: saves old clipboard, simulates Ctrl+C targeting
    the source window, then reads back. Retries if clipboard didn't change,
    because some apps (Chrome) need more time.

    Args:
        source_window: X11 window ID captured at program start, before focus shifts.

    Returns (text, capture_method).
    """
    old_clipboard = _safe_read_clipboard()

    for attempt in range(COPY_RETRIES):
        simulate_copy(source_window)
        text = read_clipboard()

        if text.strip() and text != old_clipboard:
            logger.debug("Captured text via Ctrl+C (attempt %d)", attempt + 1)
            return text, "ctrl_c"

        if attempt < COPY_RETRIES - 1:
            logger.debug("Clipboard unchanged after Ctrl+C, retrying (attempt %d)", attempt + 1)
            time.sleep(COPY_RETRY_DELAY)

    text = read_clipboard()
    if text.strip():
        logger.debug("Using clipboard content after retries (may be stale)")
        return text, "ctrl_c_fallback"

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
    logger.info("=== run_with_picker: starting picker flow ===")
    config = load_config(config_path)
    history = load_history()
    commands = build_command_list(config.pinned_commands, history)

    try:
        original_text, capture_method = _capture_selected_text(source_window)
    except ClipboardError as exc:
        logger.error("Failed to read clipboard: %s", exc)
        return False

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

    logger.info(
        "Picker result: command=%r, trigger=%s",
        picker_result.command,
        picker_result.trigger or "unknown",
    )

    return _execute_transform(
        original_text,
        picker_result.command,
        config,
        history,
        picker_result.trigger,
        source_window=source_window,
    )


def run_direct_command(
    command_label: str, config_path: Path | None = None, source_window: str | None = None
) -> bool:
    """Direct command execution without picker (for dedicated hotkeys).

    Returns True on success, False on error.
    """
    logger.info("=== run_direct_command: command=%r (dedicated hotkey) ===", command_label)
    config = load_config(config_path)
    history = load_history()

    try:
        original_text, capture_method = _capture_selected_text(source_window)
    except ClipboardError as exc:
        logger.error("Failed to read clipboard: %s", exc)
        return False

    if not original_text.strip():
        logger.warning("Clipboard is empty, nothing to transform")
        return False

    logger.debug(
        "Captured text: method=%s, length=%d, text=%s",
        capture_method,
        len(original_text),
        _truncate(original_text),
    )

    return _execute_transform(
        original_text, command_label, config, history, "direct_hotkey", source_window=source_window
    )


def _execute_transform(
    text: str,
    command_label: str,
    config: AppConfig,
    history,
    trigger: str = "",
    source_window: str | None = None,
) -> bool:
    """Transform text and paste the result. Updates history on success."""
    logger.debug("Execute transform: command=%r, trigger=%s", command_label, trigger or "unknown")

    if config.sound_enabled:
        play_sound(config.sound_acknowledge)

    try:
        result = _do_transform(text, command_label, config)
    except AIClientError as exc:
        logger.error("AI transformation failed: %s", exc)
        return False

    try:
        write_clipboard(result)
        simulate_paste(source_window)
    except ClipboardError as exc:
        logger.error("Failed to paste result: %s", exc)
        return False

    history.record_usage(command_label)
    history.save()
    logger.info("Transformation complete: command=%r, pasted result", command_label)
    return True
