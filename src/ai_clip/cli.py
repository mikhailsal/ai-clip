"""Command-line interface for ai-clip."""

from __future__ import annotations

import argparse
import logging
import sys
import typing

if typing.TYPE_CHECKING:
    from pathlib import Path

from ai_clip.config import PROJECT_DIR, load_config
from ai_clip.history import build_command_list, load_history
from ai_clip.orchestrator import run_direct_command, run_with_picker

LOG_DIR = PROJECT_DIR / "log"
LOG_FILE = LOG_DIR / "ai-clip.log"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="ai-clip",
        description="AI-powered clipboard text transformer for Linux",
    )
    parser.add_argument(
        "--command",
        type=str,
        default=None,
        help="Execute a specific command directly without showing the picker",
    )
    parser.add_argument(
        "--list-commands",
        action="store_true",
        help="List all configured commands (pinned + history)",
    )
    parser.add_argument(
        "--setup-hotkeys",
        action="store_true",
        help="Register Cinnamon hotkeys from config",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file (default: config.toml in project directory)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def _setup_logging(verbose: bool) -> None:
    """Configure logging: always write DEBUG to log file, console level depends on verbosity."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console_level = logging.DEBUG if verbose else logging.WARNING
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(console)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(file_handler)


def _list_commands(config_path: Path | None) -> None:
    """Print all configured commands."""
    config = load_config(config_path)
    history = load_history()
    commands = build_command_list(config.pinned_commands, history)

    if not commands:
        print("No commands configured. Edit your config.toml to add pinned commands.")
        return

    for i, cmd in enumerate(commands):
        pin = " [pinned]" if cmd.is_pinned else ""
        count = f" (used {cmd.count}x)" if cmd.count > 0 else ""
        print(f"  {i + 1}. {cmd.label}{pin}{count}")


def _setup_hotkeys(config_path: Path | None) -> None:
    """Register Cinnamon hotkeys from config."""
    from ai_clip.hotkeys import register_hotkeys

    config = load_config(config_path)
    register_hotkeys(config)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    from ai_clip.clipboard import _get_active_window_id

    source_window = _get_active_window_id()

    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    config_path = args.config

    if args.list_commands:
        _list_commands(config_path)
        return 0

    if args.setup_hotkeys:
        _setup_hotkeys(config_path)
        return 0

    if args.command:
        success = run_direct_command(args.command, config_path, source_window=source_window)
    else:
        success = run_with_picker(config_path, source_window=source_window)

    return 0 if success else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
