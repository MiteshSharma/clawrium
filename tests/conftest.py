"""Shared test fixtures for Clawrium tests."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config directory and set XDG_CONFIG_HOME."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def isolated_config(tmp_config_dir: Path) -> Path:
    """Return path where clawrium config should be created."""
    return tmp_config_dir / "clawrium"
