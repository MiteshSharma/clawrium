"""Tests for registry CLI commands."""

from unittest.mock import patch

from typer.testing import CliRunner

from clawrium.cli.main import app
from clawrium.core.registry import ManifestParseError, get_claw_info

runner = CliRunner()


def test_registry_list_shows_table():
    """Test that registry list shows available agent types."""
    result = runner.invoke(app, ["agent", "registry", "list"])
    assert result.exit_code == 0
    assert "openclaw" in result.output.lower()
    assert "Available Agent Types" in result.output


def test_registry_list_shows_version():
    """Test that registry list includes latest version from manifest."""
    result = runner.invoke(app, ["agent", "registry", "list"])
    assert result.exit_code == 0
    # Dynamically get expected version from registry
    claw_info = get_claw_info("openclaw")
    assert claw_info["latest_version"] in result.output


def test_registry_list_warns_on_corrupted_manifest():
    """Test registry list shows actionable warning for corrupted manifests."""
    with patch("clawrium.cli.registry.list_claws", return_value=["openclaw"]):
        with patch(
            "clawrium.cli.registry.get_claw_info",
            side_effect=ManifestParseError("broken manifest"),
        ):
            result = runner.invoke(app, ["agent", "registry", "list"])

    assert result.exit_code == 0
    assert "Corrupted manifest" in result.output
    assert "Reinstall Clawrium" in result.output


def test_registry_show_openclaw():
    """Test registry show displays agent details."""
    result = runner.invoke(app, ["agent", "registry", "show", "openclaw"])
    assert result.exit_code == 0
    assert "openclaw" in result.output.lower()
    assert "Supported Platforms" in result.output
    assert "Required Secrets" in result.output
    assert "OPENAI_API_KEY" in result.output
    assert "Optional Secrets" in result.output
    assert "ANTHROPIC_API_KEY" in result.output
    assert "ubuntu" in result.output.lower()


def test_registry_show_not_found():
    """Test registry show with unknown agent type shows error."""
    result = runner.invoke(app, ["agent", "registry", "show", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
    assert "clm agent registry" in result.output
    assert "list" in result.output


def test_registry_show_invalid_agent_type_characters():
    """Test registry show rejects invalid agent type values."""
    result = runner.invoke(app, ["agent", "registry", "show", "../etc/passwd"])
    assert result.exit_code == 1
    assert "invalid characters" in result.output.lower()


def test_registry_show_manifest_parse_error():
    """Test registry show with parse failure shows reinstall guidance."""
    with patch(
        "clawrium.cli.registry.load_manifest",
        side_effect=ManifestParseError("bad yaml"),
    ):
        result = runner.invoke(app, ["agent", "registry", "show", "openclaw"])

    assert result.exit_code == 1
    assert "corrupted" in result.output.lower()
    assert "Reinstall Clawrium" in result.output
