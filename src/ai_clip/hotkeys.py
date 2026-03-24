"""Cinnamon hotkey registration for ai-clip.

Uses dconf to register custom keybindings in Cinnamon desktop.
"""

from __future__ import annotations

import json
import logging
import subprocess
import typing

if typing.TYPE_CHECKING:
    from ai_clip.config import AppConfig

logger = logging.getLogger(__name__)

DCONF_KEYBINDING_PATH = "/org/cinnamon/desktop/keybindings/custom-keybindings"
DCONF_CUSTOM_BASE = "/org/cinnamon/desktop/keybindings/custom-keybindings/custom"


def _run_dconf(args: list[str]) -> str:
    """Run a dconf command and return stdout."""
    result = subprocess.run(
        ["dconf"] + args,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        logger.warning("dconf command failed: %s", result.stderr.strip())
    return result.stdout.strip()


def _get_existing_keybinding_slots() -> list[str]:
    """Read the current list of custom keybinding slot paths."""
    raw = _run_dconf(["read", DCONF_KEYBINDING_PATH])
    if not raw:
        return []
    try:
        return json.loads(raw.replace("'", '"'))
    except (json.JSONDecodeError, ValueError):
        return []


def _find_next_slot(existing: list[str]) -> int:
    """Find the next available custom keybinding slot number."""
    used = set()
    for path in existing:
        parts = path.rstrip("/").split("custom")
        if len(parts) > 1 and parts[-1].isdigit():
            used.add(int(parts[-1]))
    slot = 0
    while slot in used:
        slot += 1
    return slot


def _write_keybinding(slot: int, name: str, command: str, binding: str) -> None:
    """Write a single custom keybinding to dconf."""
    base = f"{DCONF_CUSTOM_BASE}{slot}/"
    _run_dconf(["write", f"{base}name", f"'{name}'"])
    _run_dconf(["write", f"{base}command", f"'{command}'"])
    _run_dconf(["write", f"{base}binding", f"['{binding}']"])


def _build_command_string(module_args: str = "") -> str:
    """Build the full command string to invoke ai-clip."""
    import sys

    python = sys.executable
    if module_args:
        return f"{python} -m ai_clip {module_args}"
    return f"{python} -m ai_clip"


def register_hotkeys(config: AppConfig) -> None:
    """Register all hotkeys from config into Cinnamon via dconf."""
    existing = _get_existing_keybinding_slots()
    next_slot = _find_next_slot(existing)
    new_slots: list[str] = []

    main_cmd = _build_command_string()
    _write_keybinding(next_slot, "ai-clip", main_cmd, config.main_hotkey)
    new_slots.append(f"{DCONF_CUSTOM_BASE}{next_slot}/")
    next_slot += 1
    logger.info("Registered main hotkey: %s -> %s", config.main_hotkey, main_cmd)

    for pinned in config.pinned_commands:
        if not pinned.dedicated_hotkey:
            continue
        cmd = _build_command_string(f'--command "{pinned.label}"')
        name = f"ai-clip: {pinned.label}"
        _write_keybinding(next_slot, name, cmd, pinned.dedicated_hotkey)
        new_slots.append(f"{DCONF_CUSTOM_BASE}{next_slot}/")
        next_slot += 1
        logger.info("Registered hotkey: %s -> %s", pinned.dedicated_hotkey, pinned.label)

    all_slots = list(set(existing + new_slots))
    slots_value = json.dumps(all_slots)
    _run_dconf(["write", DCONF_KEYBINDING_PATH, slots_value])
    print(f"Registered {len(new_slots)} hotkey(s) in Cinnamon")
