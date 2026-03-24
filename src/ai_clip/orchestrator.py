"""Main orchestration flow for ai-clip.

Coordinates: clipboard capture -> command selection -> AI transformation -> paste back.
"""

from __future__ import annotations

import logging
import typing

if typing.TYPE_CHECKING:
    from pathlib import Path

from ai_clip.ai_client import AIClientError, transform_text
from ai_clip.clipboard import (
    ClipboardError,
    read_clipboard,
    read_primary_selection,
    simulate_copy,
    simulate_paste,
    write_clipboard,
)
from ai_clip.config import AppConfig, load_config
from ai_clip.history import build_command_list, load_history
from ai_clip.picker import PickerResult, show_picker

logger = logging.getLogger(__name__)


def _capture_selected_text() -> str:
    """Capture the currently selected text, trying primary selection first.

    The X11 primary selection contains highlighted text without needing Ctrl+C.
    Falls back to Ctrl+C if primary selection is empty.
    """
    try:
        primary = read_primary_selection()
        if primary.strip():
            return primary
    except ClipboardError:
        pass

    simulate_copy()
    return read_clipboard()


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

    logger.info("Transforming with command=%r, model=%s", command_label, model)
    return transform_text(
        text=text,
        command_prompt=prompt,
        api_key=config.openrouter_api_key,
        model=model,
        timeout=config.timeout_seconds,
    )


def run_with_picker(config_path: Path | None = None) -> bool:
    """Full interactive flow: copy -> pick command -> AI -> paste.

    Returns True on success, False on cancellation or error.
    """
    config = load_config(config_path)
    history = load_history()
    commands = build_command_list(config.pinned_commands, history)

    try:
        original_text = _capture_selected_text()
    except ClipboardError as exc:
        logger.error("Failed to read clipboard: %s", exc)
        return False

    if not original_text.strip():
        logger.warning("Clipboard is empty, nothing to transform")
        return False

    picker_result: PickerResult = show_picker(commands)
    if picker_result.cancelled or not picker_result.command:
        logger.info("User cancelled")
        return False

    return _execute_transform(original_text, picker_result.command, config, history)


def run_direct_command(command_label: str, config_path: Path | None = None) -> bool:
    """Direct command execution without picker (for dedicated hotkeys).

    Returns True on success, False on error.
    """
    config = load_config(config_path)
    history = load_history()

    try:
        original_text = _capture_selected_text()
    except ClipboardError as exc:
        logger.error("Failed to read clipboard: %s", exc)
        return False

    if not original_text.strip():
        logger.warning("Clipboard is empty, nothing to transform")
        return False

    return _execute_transform(original_text, command_label, config, history)


def _execute_transform(
    text: str,
    command_label: str,
    config: AppConfig,
    history,
) -> bool:
    """Transform text and paste the result. Updates history on success."""
    try:
        result = _do_transform(text, command_label, config)
    except AIClientError as exc:
        logger.error("AI transformation failed: %s", exc)
        return False

    try:
        write_clipboard(result)
        simulate_paste()
    except ClipboardError as exc:
        logger.error("Failed to paste result: %s", exc)
        return False

    history.record_usage(command_label)
    history.save()
    logger.info("Transformation complete, pasted result")
    return True
