"""Tests for the config module."""

from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w

from ai_clip.config import (
    DEFAULT_ACKNOWLEDGE_SOUND,
    DEFAULT_SOUND_ENABLED,
    AppConfig,
    ConfigError,
    PinnedCommand,
    _load_from_toml,
    _parse_pinned_commands,
    generate_default_config,
    load_config,
)


def _write_toml(path: Path, data: dict) -> None:
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


class TestParsePinnedCommands:
    def test_valid_commands(self):
        raw = [
            {"label": "Fix", "prompt": "Fix text"},
            {"label": "Translate", "prompt": "Translate text", "model": "gpt-4"},
        ]
        result = _parse_pinned_commands(raw)
        assert len(result) == 2
        assert result[0].label == "Fix"
        assert result[1].model == "gpt-4"

    def test_skips_missing_label(self):
        raw = [{"prompt": "Do something"}]
        result = _parse_pinned_commands(raw)
        assert len(result) == 0

    def test_skips_missing_prompt(self):
        raw = [{"label": "Do"}]
        result = _parse_pinned_commands(raw)
        assert len(result) == 0

    def test_skips_non_dict(self):
        raw = ["not a dict", 42]
        result = _parse_pinned_commands(raw)
        assert len(result) == 0

    def test_dedicated_hotkey(self):
        raw = [{"label": "T", "prompt": "P", "dedicated_hotkey": "<Super>t"}]
        result = _parse_pinned_commands(raw)
        assert result[0].dedicated_hotkey == "<Super>t"

    def test_empty_list(self):
        assert _parse_pinned_commands([]) == []

    def test_strips_whitespace(self):
        raw = [{"label": "  Fix  ", "prompt": "  Fix text  "}]
        result = _parse_pinned_commands(raw)
        assert result[0].label == "Fix"
        assert result[0].prompt == "Fix text"


class TestLoadFromToml:
    def test_valid_file(self, tmp_path):
        toml_path = tmp_path / "config.toml"
        _write_toml(toml_path, {"api": {"key": "val"}})
        data = _load_from_toml(toml_path)
        assert data["api"]["key"] == "val"

    def test_missing_file(self, tmp_path):
        data = _load_from_toml(tmp_path / "nonexistent.toml")
        assert data == {}

    def test_invalid_toml(self, tmp_path):
        toml_path = tmp_path / "bad.toml"
        toml_path.write_text("invalid [[[toml")
        with pytest.raises(ConfigError, match="Invalid TOML"):
            _load_from_toml(toml_path)


class TestLoadConfig:
    def test_full_config(self, tmp_path):
        config_path = tmp_path / "config.toml"
        _write_toml(
            config_path,
            {
                "api": {
                    "openrouter_api_key": "sk-test",
                    "default_model": "gpt-4o",
                    "timeout_seconds": 15,
                },
                "main_hotkey": "<Super>x",
                "commands": {
                    "pinned": [{"label": "Fix", "prompt": "Fix it"}],
                },
            },
        )
        cfg = load_config(config_path)
        assert cfg.openrouter_api_key == "sk-test"
        assert cfg.default_model == "gpt-4o"
        assert cfg.timeout_seconds == 15
        assert cfg.main_hotkey == "<Super>x"
        assert len(cfg.pinned_commands) == 1
        assert cfg.pinned_commands[0].label == "Fix"

    def test_env_fallback(self, tmp_path):
        config_path = tmp_path / "empty.toml"
        _write_toml(config_path, {})
        env = {"OPENROUTER_API_KEY": "sk-env", "AI_CLIP_DEFAULT_MODEL": "claude-3"}
        with patch.dict("os.environ", env, clear=False):
            cfg = load_config(config_path)
        assert cfg.openrouter_api_key == "sk-env"
        assert cfg.default_model == "claude-3"

    def test_defaults_when_no_file(self, tmp_path):
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.default_model == "google/gemini-2.0-flash-001"
        assert cfg.timeout_seconds == 30
        assert cfg.pinned_commands == []

    def test_toml_overrides_env(self, tmp_path):
        config_path = tmp_path / "config.toml"
        _write_toml(config_path, {"api": {"openrouter_api_key": "sk-toml"}})
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-env"}, clear=False):
            cfg = load_config(config_path)
        assert cfg.openrouter_api_key == "sk-toml"

    def test_config_path_stored(self, tmp_path):
        config_path = tmp_path / "config.toml"
        _write_toml(config_path, {})
        cfg = load_config(config_path)
        assert cfg.config_path == config_path

    def test_none_path_uses_default(self):
        from ai_clip.config import DEFAULT_CONFIG_PATH

        with patch("ai_clip.config._load_from_toml", return_value={}):
            cfg = load_config(None)
        assert cfg.config_path == DEFAULT_CONFIG_PATH

    def test_sound_config(self, tmp_path):
        config_path = tmp_path / "config.toml"
        _write_toml(
            config_path,
            {
                "sound": {
                    "enabled": False,
                    "acknowledge_sound": "/custom/beep.oga",
                },
            },
        )
        cfg = load_config(config_path)
        assert cfg.sound_enabled is False
        assert cfg.sound_acknowledge == "/custom/beep.oga"

    def test_sound_defaults_when_missing(self, tmp_path):
        config_path = tmp_path / "config.toml"
        _write_toml(config_path, {})
        cfg = load_config(config_path)
        assert cfg.sound_enabled is DEFAULT_SOUND_ENABLED
        assert cfg.sound_acknowledge == DEFAULT_ACKNOWLEDGE_SOUND


class TestGenerateDefaultConfig:
    def test_creates_config(self, tmp_path):
        config_path = tmp_path / "sub" / "config.toml"
        result = generate_default_config(config_path)
        assert result == config_path
        assert config_path.exists()
        cfg = load_config(config_path)
        assert len(cfg.pinned_commands) == 2
        assert cfg.pinned_commands[0].label == "Translate to English"

    def test_does_not_overwrite(self, tmp_path):
        config_path = tmp_path / "config.toml"
        _write_toml(config_path, {"api": {"openrouter_api_key": "original"}})
        generate_default_config(config_path)
        cfg = load_config(config_path)
        assert cfg.openrouter_api_key == "original"

    def test_returns_path(self, tmp_path):
        config_path = tmp_path / "config.toml"
        result = generate_default_config(config_path)
        assert result == config_path


class TestDataclasses:
    def test_pinned_command_defaults(self):
        cmd = PinnedCommand(label="Test", prompt="Do test")
        assert cmd.dedicated_hotkey is None
        assert cmd.model is None

    def test_app_config_defaults(self):
        cfg = AppConfig()
        assert cfg.openrouter_api_key == ""
        assert cfg.pinned_commands == []
        assert cfg.timeout_seconds == 30
        assert cfg.sound_enabled is True
        assert cfg.sound_acknowledge == DEFAULT_ACKNOWLEDGE_SOUND
