"""Tests for config directory management."""

import os
from pathlib import Path

import pytest

from clawrium.core.config import get_config_dir, init_config_dir


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_returns_path_ending_in_clawrium(self, tmp_config_dir: Path) -> None:
        """Config dir path should end with 'clawrium'."""
        result = get_config_dir()
        assert result.name == "clawrium"

    def test_uses_xdg_config_home_when_set(self, tmp_config_dir: Path) -> None:
        """Should use XDG_CONFIG_HOME environment variable."""
        result = get_config_dir()
        assert result == tmp_config_dir / "clawrium"

    def test_falls_back_to_home_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should fall back to ~/.config when XDG_CONFIG_HOME not set."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = get_config_dir()
        assert result == Path.home() / ".config" / "clawrium"

    def test_ignores_relative_xdg_config_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should ignore XDG_CONFIG_HOME if it's a relative path."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")
        result = get_config_dir()
        assert result == Path.home() / ".config" / "clawrium"


class TestInitConfigDir:
    """Tests for init_config_dir function."""

    def test_creates_directory(self, isolated_config: Path) -> None:
        """Should create the config directory."""
        assert not isolated_config.exists()
        result = init_config_dir()
        assert isolated_config.exists()
        assert isolated_config.is_dir()

    def test_returns_created_path(self, isolated_config: Path) -> None:
        """Should return the path to the created directory."""
        result = init_config_dir()
        assert result == isolated_config

    def test_idempotent(self, isolated_config: Path) -> None:
        """Should not error if directory already exists."""
        init_config_dir()
        # Second call should not raise
        result = init_config_dir()
        assert result == isolated_config
        assert isolated_config.is_dir()
