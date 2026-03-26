"""Configuration management for ai-clip.

Loads from config.toml in the project directory with environment variable fallbacks.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import tomli
import tomli_w

logger = logging.getLogger(__name__)


def _find_project_dir() -> Path:
    """Find the project root by walking up from this file until pyproject.toml is found."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()


PROJECT_DIR = _find_project_dir()
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config.toml"
DEFAULT_HISTORY_PATH = PROJECT_DIR / "history.json"
DEFAULT_MODEL = "google/gemini-2.0-flash-001"
DEFAULT_TIMEOUT = 30
DEFAULT_MAIN_HOTKEY = "<Super><Shift>a"
DEFAULT_SOUND_ENABLED = True
DEFAULT_ACKNOWLEDGE_SOUND = "/usr/share/sounds/freedesktop/stereo/message.oga"


@dataclass
class PinnedCommand:
    label: str
    prompt: str
    dedicated_hotkey: str | None = None
    model: str | None = None


@dataclass
class AppConfig:
    openrouter_api_key: str = ""
    default_model: str = DEFAULT_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT
    main_hotkey: str = DEFAULT_MAIN_HOTKEY
    sound_enabled: bool = DEFAULT_SOUND_ENABLED
    sound_acknowledge: str = DEFAULT_ACKNOWLEDGE_SOUND
    pinned_commands: list[PinnedCommand] = field(default_factory=list)
    config_path: Path = DEFAULT_CONFIG_PATH


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


def _parse_pinned_commands(raw_commands: list[dict]) -> list[PinnedCommand]:
    """Parse raw TOML pinned command dicts into PinnedCommand objects."""
    result = []
    for cmd in raw_commands:
        if not isinstance(cmd, dict):
            continue
        label = cmd.get("label", "").strip()
        prompt = cmd.get("prompt", "").strip()
        if not label or not prompt:
            logger.warning("Skipping pinned command missing label or prompt: %s", cmd)
            continue
        result.append(
            PinnedCommand(
                label=label,
                prompt=prompt,
                dedicated_hotkey=cmd.get("dedicated_hotkey"),
                model=cmd.get("model"),
            )
        )
    return result


def _load_from_toml(config_path: Path) -> dict:
    """Read and parse a TOML config file."""
    try:
        with open(config_path, "rb") as f:
            return tomli.load(f)
    except FileNotFoundError:
        logger.info("Config file not found: %s", config_path)
        return {}
    except tomli.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {config_path}: {exc}") from exc


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from TOML file with env variable fallbacks."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    data = _load_from_toml(path)

    api_section = data.get("api", {})
    commands_section = data.get("commands", {})
    sound_section = data.get("sound", {})

    api_key = api_section.get(
        "openrouter_api_key",
        os.environ.get("OPENROUTER_API_KEY", ""),
    )
    default_model = api_section.get(
        "default_model",
        os.environ.get("AI_CLIP_DEFAULT_MODEL", DEFAULT_MODEL),
    )
    timeout = api_section.get("timeout_seconds", DEFAULT_TIMEOUT)
    main_hotkey = data.get("main_hotkey", DEFAULT_MAIN_HOTKEY)

    sound_enabled = sound_section.get("enabled", DEFAULT_SOUND_ENABLED)
    sound_acknowledge = sound_section.get("acknowledge_sound", DEFAULT_ACKNOWLEDGE_SOUND)

    pinned = _parse_pinned_commands(commands_section.get("pinned", []))

    return AppConfig(
        openrouter_api_key=api_key,
        default_model=default_model,
        timeout_seconds=int(timeout),
        main_hotkey=main_hotkey,
        sound_enabled=sound_enabled,
        sound_acknowledge=sound_acknowledge,
        pinned_commands=pinned,
        config_path=path,
    )


def generate_default_config(config_path: Path | None = None) -> Path:
    """Generate a default config file if it doesn't exist. Returns the path."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        logger.info("Config already exists: %s", path)
        return path

    path.parent.mkdir(parents=True, exist_ok=True)

    default_data = {
        "api": {
            "openrouter_api_key": "sk-or-your-key-here",
            "default_model": DEFAULT_MODEL,
            "timeout_seconds": DEFAULT_TIMEOUT,
        },
        "main_hotkey": DEFAULT_MAIN_HOTKEY,
        "commands": {
            "pinned": [
                {
                    "label": "Translate to English",
                    "prompt": (
                        "Translate the following text to English. Return only the translated text."
                    ),
                    "dedicated_hotkey": "<Super><Shift>e",
                },
                {
                    "label": "Fix punctuation & grammar",
                    "prompt": (
                        "Fix punctuation and grammar in the following text. "
                        "Return only the corrected text."
                    ),
                },
            ]
        },
    }

    with open(path, "wb") as f:
        tomli_w.dump(default_data, f)

    logger.info("Generated default config: %s", path)
    return path
