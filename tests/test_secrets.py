"""Tests for secrets storage module."""

import json
import pytest
from clawrium.core.secrets import (
    load_secrets,
    save_secrets,
    get_secret,
    set_secret,
    remove_secret,
    list_secrets,
    SECRETS_FILE,
    SecretEntry,
    SecretsFileCorruptedError,
    DuplicateSecretError,
)


def test_load_secrets_no_file(isolated_config):
    """load_secrets() with no file returns empty dict."""
    secrets = load_secrets()
    assert secrets == {}


def test_load_secrets_valid_json(isolated_config):
    """load_secrets() with valid JSON returns dict[str, SecretEntry]."""
    # Setup: create secrets.json with test data
    isolated_config.mkdir(parents=True, exist_ok=True)
    secrets_path = isolated_config / SECRETS_FILE
    test_data = {
        "OPENAI_API_KEY": {
            "key": "OPENAI_API_KEY",
            "value": "sk-test-123",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "description": "OpenAI API key",
        },
        "ANTHROPIC_API_KEY": {
            "key": "ANTHROPIC_API_KEY",
            "value": "sk-ant-test-456",
            "created_at": "2024-01-02T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "description": "",
        },
    }
    secrets_path.write_text(json.dumps(test_data))

    # Test
    secrets = load_secrets()
    assert secrets == test_data


def test_load_secrets_invalid_json(isolated_config):
    """load_secrets() with invalid JSON raises SecretsFileCorruptedError."""
    isolated_config.mkdir(parents=True, exist_ok=True)
    secrets_path = isolated_config / SECRETS_FILE
    secrets_path.write_text("not valid json {{{")

    with pytest.raises(SecretsFileCorruptedError) as exc_info:
        load_secrets()
    assert "corrupted" in str(exc_info.value).lower()


def test_save_secrets_creates_file(isolated_config):
    """save_secrets() creates file in config dir."""
    test_secrets = {
        "OPENAI_API_KEY": {
            "key": "OPENAI_API_KEY",
            "value": "sk-test-123",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "description": "OpenAI API key",
        }
    }

    save_secrets(test_secrets)

    secrets_path = isolated_config / SECRETS_FILE
    assert secrets_path.exists()

    with open(secrets_path) as f:
        saved_data = json.load(f)
    assert saved_data == test_secrets


def test_save_secrets_file_permissions(isolated_config):
    """save_secrets() creates file with mode 0o600."""
    test_secrets = {
        "OPENAI_API_KEY": {
            "key": "OPENAI_API_KEY",
            "value": "sk-test-123",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "description": "OpenAI API key",
        }
    }
    save_secrets(test_secrets)

    secrets_path = isolated_config / SECRETS_FILE
    mode = secrets_path.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


def test_save_secrets_creates_dir(tmp_path, monkeypatch):
    """save_secrets creates config directory if it doesn't exist."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    config_dir = tmp_path / "clawrium"

    # Config dir doesn't exist yet
    assert not config_dir.exists()

    test_secrets = {
        "OPENAI_API_KEY": {
            "key": "OPENAI_API_KEY",
            "value": "sk-test-123",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "description": "OpenAI API key",
        }
    }
    save_secrets(test_secrets)

    # Config dir should now exist
    assert config_dir.exists()
    assert (config_dir / SECRETS_FILE).exists()


def test_set_secret_creates_entry(isolated_config):
    """set_secret(key, value, description) creates entry with timestamps."""
    from datetime import datetime

    # Create new secret
    result = set_secret("OPENAI_API_KEY", "sk-test-123", "OpenAI API key")
    assert result is True  # Created new

    # Verify entry was created
    secret = get_secret("OPENAI_API_KEY")
    assert secret is not None
    assert secret["key"] == "OPENAI_API_KEY"
    assert secret["value"] == "sk-test-123"
    assert secret["description"] == "OpenAI API key"
    # Verify timestamps are ISO 8601
    assert "T" in secret["created_at"]
    assert "Z" in secret["created_at"] or "+" in secret["created_at"]
    assert secret["created_at"] == secret["updated_at"]


def test_set_secret_updates_existing(isolated_config):
    """set_secret(key, value) on existing key updates updated_at, preserves created_at."""
    # Create initial secret
    set_secret("OPENAI_API_KEY", "sk-test-123", "OpenAI API key")
    secret1 = get_secret("OPENAI_API_KEY")
    created_at = secret1["created_at"]

    import time

    time.sleep(0.1)  # Ensure timestamp difference

    # Update existing secret
    result = set_secret("OPENAI_API_KEY", "sk-test-456")
    assert result is False  # Updated existing

    # Verify update
    secret2 = get_secret("OPENAI_API_KEY")
    assert secret2 is not None
    assert secret2["value"] == "sk-test-456"
    assert secret2["created_at"] == created_at  # Preserved
    assert secret2["updated_at"] != created_at  # Changed
    # Description preserved if not provided
    assert secret2["description"] == "OpenAI API key"


def test_set_secret_default_description(isolated_config):
    """set_secret(key, value) without description sets empty string."""
    set_secret("TEST_KEY", "test-value")

    secret = get_secret("TEST_KEY")
    assert secret is not None
    assert secret["description"] == ""


def test_get_secret_not_found(isolated_config):
    """get_secret(key) returns None if key not found."""
    secret = get_secret("NONEXISTENT_KEY")
    assert secret is None


def test_remove_secret_found(isolated_config):
    """remove_secret(key) removes entry, returns True."""
    # Setup: create secret
    set_secret("OPENAI_API_KEY", "sk-test-123")

    # Remove
    result = remove_secret("OPENAI_API_KEY")
    assert result is True

    # Verify removed
    secret = get_secret("OPENAI_API_KEY")
    assert secret is None


def test_remove_secret_not_found(isolated_config):
    """remove_secret(key) returns False if not found."""
    result = remove_secret("NONEXISTENT_KEY")
    assert result is False


def test_list_secrets(isolated_config):
    """list_secrets() returns sorted list of keys (not values)."""
    # Setup: create multiple secrets
    set_secret("OPENAI_API_KEY", "sk-test-123")
    set_secret("ANTHROPIC_API_KEY", "sk-ant-456")
    set_secret("ZEROCLAW_TOKEN", "zc-789")

    # Get list
    keys = list_secrets()

    # Verify
    assert keys == ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ZEROCLAW_TOKEN"]  # Sorted
    assert "sk-test-123" not in keys  # Values not included


def test_list_secrets_empty(isolated_config):
    """list_secrets() returns empty list when no secrets."""
    keys = list_secrets()
    assert keys == []


def test_concurrent_write_protection(isolated_config):
    """Multiple save_secrets calls don't corrupt file (file locking test)."""
    # This is a basic sanity check - true concurrency testing requires threading
    test_secrets1 = {
        "KEY1": {
            "key": "KEY1",
            "value": "value1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "description": "",
        }
    }
    test_secrets2 = {
        "KEY2": {
            "key": "KEY2",
            "value": "value2",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "description": "",
        }
    }

    # Sequential writes should both succeed
    save_secrets(test_secrets1)
    save_secrets(test_secrets2)

    # Last write wins
    secrets = load_secrets()
    assert "KEY2" in secrets
