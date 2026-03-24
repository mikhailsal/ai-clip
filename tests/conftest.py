"""Shared test fixtures for ai-clip."""

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Provide a temporary config directory."""
    config_dir = tmp_path / "ai-clip"
    config_dir.mkdir()
    return config_dir
