"""Tests for CLI host commands."""

import os
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from clawrium.cli.main import app

runner = CliRunner()


def test_host_add_success(isolated_config: Path, mock_ssh_client, mock_ansible_runner):
    """clm host add with valid connection saves host."""
    with patch('clawrium.core.ssh_connection.paramiko.SSHClient', return_value=mock_ssh_client):
        with patch('clawrium.core.hardware.ansible_runner.run', return_value=mock_ansible_runner):
            result = runner.invoke(app, ["host", "add", "192.168.1.100"], env=os.environ)

            assert result.exit_code == 0
            assert "192.168.1.100" in result.output or "success" in result.output.lower()


def test_host_add_with_flags(isolated_config: Path, mock_ssh_client, mock_ansible_runner):
    """clm host add with flags uses provided values."""
    with patch('clawrium.core.ssh_connection.paramiko.SSHClient', return_value=mock_ssh_client):
        with patch('clawrium.core.hardware.ansible_runner.run', return_value=mock_ansible_runner):
            result = runner.invoke(
                app,
                ["host", "add", "192.168.1.100", "--user", "xclm", "--port", "22", "--alias", "myhost"],
                env=os.environ
            )

            assert result.exit_code == 0


def test_host_add_connection_failed(isolated_config: Path, mock_ssh_client_fail):
    """clm host add with connection failure shows error, exits 1."""
    with patch('clawrium.core.ssh_connection.paramiko.SSHClient', return_value=mock_ssh_client_fail):
        result = runner.invoke(app, ["host", "add", "badhost"], env=os.environ)

        assert result.exit_code == 1
        assert "authentication" in result.output.lower() or "failed" in result.output.lower()


def test_host_add_duplicate(isolated_config: Path, sample_host_data: dict):
    """Adding same hostname twice shows error, exits 1."""
    # Setup: create hosts.json with existing host
    isolated_config.mkdir(parents=True, exist_ok=True)
    import json
    hosts_file = isolated_config / "hosts.json"
    hosts_file.write_text(json.dumps([sample_host_data]))

    result = runner.invoke(app, ["host", "add", "192.168.1.100"], env=os.environ)

    assert result.exit_code == 1
    assert "already" in result.output.lower() or "exists" in result.output.lower()


def test_host_list_empty(isolated_config: Path):
    """clm host list with no hosts shows 'No hosts registered'."""
    # Ensure config dir exists but no hosts.json
    isolated_config.mkdir(parents=True, exist_ok=True)

    result = runner.invoke(app, ["host", "list"], env=os.environ)

    assert result.exit_code == 0
    assert "no hosts" in result.output.lower() or "empty" in result.output.lower()


def test_host_list_table(isolated_config: Path, sample_host_data: dict):
    """clm host list with hosts shows table with Alias, Host, Architecture columns."""
    # Setup: create hosts.json with sample data
    isolated_config.mkdir(parents=True, exist_ok=True)
    import json
    hosts_file = isolated_config / "hosts.json"
    hosts_file.write_text(json.dumps([sample_host_data]))

    result = runner.invoke(app, ["host", "list"], env=os.environ)

    assert result.exit_code == 0
    # Check for table headers
    assert "alias" in result.output.lower() or "host" in result.output.lower()
    # Check for sample data
    assert "testhost" in result.output.lower() or "192.168.1.100" in result.output


@pytest.mark.xfail(reason="Not implemented")
def test_host_remove_with_confirmation(isolated_config: Path, sample_host_data: dict, monkeypatch):
    """clm host remove prompts for confirmation."""
    # Setup: create hosts.json with sample data
    isolated_config.mkdir(parents=True, exist_ok=True)
    import json
    hosts_file = isolated_config / "hosts.json"
    hosts_file.write_text(json.dumps([sample_host_data]))

    # Mock confirmation to abort
    result = runner.invoke(app, ["host", "remove", "192.168.1.100"], input="n\n", env=os.environ)

    assert "confirm" in result.output.lower() or "remove" in result.output.lower()


@pytest.mark.xfail(reason="Not implemented")
def test_host_remove_force(isolated_config: Path, sample_host_data: dict):
    """clm host remove --force skips confirmation."""
    # Setup: create hosts.json with sample data
    isolated_config.mkdir(parents=True, exist_ok=True)
    import json
    hosts_file = isolated_config / "hosts.json"
    hosts_file.write_text(json.dumps([sample_host_data]))

    result = runner.invoke(app, ["host", "remove", "192.168.1.100", "--force"], env=os.environ)

    assert result.exit_code == 0
    # Should not prompt for confirmation
    assert "removed" in result.output.lower() or "success" in result.output.lower()


@pytest.mark.xfail(reason="Not implemented")
def test_host_remove_not_found(isolated_config: Path):
    """clm host remove nonexistent shows error, exits 1."""
    # Ensure config dir exists but no hosts
    isolated_config.mkdir(parents=True, exist_ok=True)

    result = runner.invoke(app, ["host", "remove", "nonexistent"], env=os.environ)

    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "error" in result.output.lower()


@pytest.mark.xfail(reason="Not implemented")
def test_host_status_connected(isolated_config: Path, sample_host_data: dict, mock_ssh_client):
    """clm host status with reachable host shows 'Connected'."""
    # Setup: create hosts.json with sample data
    isolated_config.mkdir(parents=True, exist_ok=True)
    import json
    hosts_file = isolated_config / "hosts.json"
    hosts_file.write_text(json.dumps([sample_host_data]))

    with patch('paramiko.SSHClient', return_value=mock_ssh_client):
        result = runner.invoke(app, ["host", "status", "192.168.1.100"], env=os.environ)

        assert result.exit_code == 0
        assert "connected" in result.output.lower()


@pytest.mark.xfail(reason="Not implemented")
def test_host_status_disconnected(isolated_config: Path, sample_host_data: dict, mock_ssh_client_fail):
    """clm host status with unreachable host shows 'Disconnected'."""
    # Setup: create hosts.json with sample data
    isolated_config.mkdir(parents=True, exist_ok=True)
    import json
    hosts_file = isolated_config / "hosts.json"
    hosts_file.write_text(json.dumps([sample_host_data]))

    with patch('paramiko.SSHClient', return_value=mock_ssh_client_fail):
        result = runner.invoke(app, ["host", "status", "192.168.1.100"], env=os.environ)

        # May exit 0 and show "disconnected" status, or exit 1 depending on design
        assert "disconnected" in result.output.lower() or "failed" in result.output.lower()


@pytest.mark.xfail(reason="Not implemented")
def test_host_status_refresh(isolated_config: Path, sample_host_data: dict, mock_ssh_client, mock_ansible_runner):
    """clm host status --refresh updates hardware info."""
    # Setup: create hosts.json with sample data
    isolated_config.mkdir(parents=True, exist_ok=True)
    import json
    hosts_file = isolated_config / "hosts.json"
    hosts_file.write_text(json.dumps([sample_host_data]))

    with patch('paramiko.SSHClient', return_value=mock_ssh_client):
        with patch('ansible_runner.run', return_value=mock_ansible_runner):
            result = runner.invoke(app, ["host", "status", "192.168.1.100", "--refresh"], env=os.environ)

            assert result.exit_code == 0
            assert "hardware" in result.output.lower() or "refresh" in result.output.lower()
