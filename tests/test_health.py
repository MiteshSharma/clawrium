"""Tests for claw health checking."""

import pytest
from unittest.mock import patch, MagicMock

from clawrium.core.health import (
    check_claw_health,
    check_all_claws_on_host,
    ClawStatus,
)


@pytest.fixture
def mock_host():
    """Host record with installed claw."""
    return {
        "hostname": "192.168.1.100",
        "port": 22,
        "user": "xclm",
        "key_id": "testhost",
        "claws": {
            "openclaw": {
                "version": "0.1.0",
                "status": "installed",
                "user": "opc-testhost",
            }
        },
    }


def test_health_check_running(mock_host):
    """Process running returns RUNNING status."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "RUNNING"}}}
    ]

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            # Mock no required secrets for openclaw
            with patch("clawrium.core.health.get_required_secrets", return_value=[]):
                result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.RUNNING
    assert result["claw"] == "openclaw"
    assert result["user"] == "opc-testhost"
    assert result["error"] is None
    assert result["missing_secrets"] is None


def test_health_check_stopped(mock_host):
    """Process not running returns STOPPED status."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "STOPPED"}}}
    ]

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.STOPPED


def test_health_check_ssh_fails(mock_host):
    """SSH failure returns UNKNOWN status with error."""
    mock_runner = MagicMock()
    mock_runner.status = "failed"
    mock_runner.events = []

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.UNKNOWN
    assert "SSH failed" in result["error"]


def test_health_check_not_installed(mock_host):
    """Claw not in host record returns NOT_INSTALLED."""
    result = check_claw_health("zeroclaw", mock_host)

    assert result["status"] == ClawStatus.NOT_INSTALLED


def test_health_check_no_ssh_key(mock_host):
    """Missing SSH key returns UNKNOWN."""
    with patch("clawrium.core.health.get_host_private_key", return_value=None):
        result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.UNKNOWN
    assert "SSH key not found" in result["error"]


def test_health_check_timeout(mock_host):
    """Timeout returns UNKNOWN status."""
    mock_runner = MagicMock()
    mock_runner.status = "timeout"
    mock_runner.events = []

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.UNKNOWN
    assert "timed out" in result["error"]


def test_check_all_claws_on_host(mock_host):
    """check_all_claws_on_host returns results for each claw."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "RUNNING"}}}
    ]

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            # Mock no required secrets for openclaw
            with patch("clawrium.core.health.get_required_secrets", return_value=[]):
                results = check_all_claws_on_host(mock_host)

    assert len(results) == 1
    assert results[0]["claw"] == "openclaw"
    assert results[0]["status"] == ClawStatus.RUNNING


def test_health_check_no_claw_user():
    """Missing claw user returns UNKNOWN status with error."""
    host = {
        "hostname": "192.168.1.100",
        "claws": {
            "openclaw": {
                "version": "0.1.0",
                "status": "installed",
                # No "user" field
            }
        },
    }

    result = check_claw_health("openclaw", host)

    assert result["status"] == ClawStatus.UNKNOWN
    assert "No claw user recorded" in result["error"]


def test_health_check_invalid_claw_user():
    """Invalid claw user format returns UNKNOWN status with error."""
    host = {
        "hostname": "192.168.1.100",
        "claws": {
            "openclaw": {
                "version": "0.1.0",
                "status": "installed",
                "user": "root; rm -rf /",  # Command injection attempt
            }
        },
    }

    result = check_claw_health("openclaw", host)

    assert result["status"] == ClawStatus.UNKNOWN
    assert "Invalid claw user format" in result["error"]


def test_health_check_host_unreachable(mock_host):
    """Host unreachable returns UNKNOWN status."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"  # ansible-runner returns successful even for unreachable
    mock_runner.events = [
        {"event": "runner_on_unreachable", "event_data": {}}
    ]

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.UNKNOWN
    assert "unreachable" in result["error"].lower()


def test_health_check_unexpected_output(mock_host):
    """Unexpected output returns UNKNOWN status."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "UNEXPECTED_OUTPUT"}}}
    ]

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.UNKNOWN
    assert "Unexpected output" in result["error"]


def test_claw_status_degraded_exists():
    """ClawStatus.DEGRADED enum value exists."""
    assert hasattr(ClawStatus, "DEGRADED")
    assert ClawStatus.DEGRADED == "degraded"


def test_health_result_has_missing_secrets_field(mock_host):
    """HealthResult includes missing_secrets field in return."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "RUNNING"}}}
    ]

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            with patch("clawrium.core.health.get_instance_secrets", return_value={"OPENAI_API_KEY": {}}):
                with patch("clawrium.core.health.get_required_secrets", return_value=[]):
                    result = check_claw_health("openclaw", mock_host)

    # Check field exists
    assert "missing_secrets" in result


def test_check_claw_health_degraded_when_missing_secrets(mock_host):
    """Running claw with missing required secrets returns DEGRADED status."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "RUNNING"}}}
    ]

    # Mock required secrets for openclaw
    required_secrets = [
        {"key": "OPENAI_API_KEY", "description": "OpenAI API key"},
        {"key": "ANTHROPIC_API_KEY", "description": "Anthropic API key"},
    ]

    # Mock empty instance secrets (all missing)
    instance_secrets = {}

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            with patch("clawrium.core.health.get_instance_secrets", return_value=instance_secrets):
                with patch("clawrium.core.health.get_required_secrets", return_value=required_secrets):
                    result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.DEGRADED
    assert result["missing_secrets"] is not None
    assert len(result["missing_secrets"]) == 2
    assert "OPENAI_API_KEY" in result["missing_secrets"]
    assert "ANTHROPIC_API_KEY" in result["missing_secrets"]


def test_check_claw_health_running_when_all_secrets_present(mock_host):
    """Running claw with all required secrets returns RUNNING status."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "RUNNING"}}}
    ]

    # Mock required secrets for openclaw
    required_secrets = [
        {"key": "OPENAI_API_KEY", "description": "OpenAI API key"},
    ]

    # Mock instance secrets (all present)
    instance_secrets = {
        "OPENAI_API_KEY": {
            "key": "OPENAI_API_KEY",
            "value": "sk-test",
            "created_at": "2026-03-22T00:00:00Z",
            "updated_at": "2026-03-22T00:00:00Z",
            "description": "",
        }
    }

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            with patch("clawrium.core.health.get_instance_secrets", return_value=instance_secrets):
                with patch("clawrium.core.health.get_required_secrets", return_value=required_secrets):
                    result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.RUNNING
    assert result["missing_secrets"] is None


def test_check_claw_health_degraded_partial_secrets(mock_host):
    """Running claw with some missing secrets returns DEGRADED."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "RUNNING"}}}
    ]

    # Mock required secrets for openclaw
    required_secrets = [
        {"key": "OPENAI_API_KEY", "description": "OpenAI API key"},
        {"key": "ANTHROPIC_API_KEY", "description": "Anthropic API key"},
    ]

    # Mock partial instance secrets (one present, one missing)
    instance_secrets = {
        "OPENAI_API_KEY": {
            "key": "OPENAI_API_KEY",
            "value": "sk-test",
            "created_at": "2026-03-22T00:00:00Z",
            "updated_at": "2026-03-22T00:00:00Z",
            "description": "",
        }
    }

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            with patch("clawrium.core.health.get_instance_secrets", return_value=instance_secrets):
                with patch("clawrium.core.health.get_required_secrets", return_value=required_secrets):
                    result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.DEGRADED
    assert result["missing_secrets"] == ["ANTHROPIC_API_KEY"]


def test_missing_secrets_none_for_stopped_status(mock_host):
    """STOPPED status has missing_secrets as None."""
    mock_runner = MagicMock()
    mock_runner.status = "successful"
    mock_runner.events = [
        {"event": "runner_on_ok", "event_data": {"res": {"stdout": "STOPPED"}}}
    ]

    with patch("clawrium.core.health.get_host_private_key", return_value="/fake/key"):
        with patch("clawrium.core.health.ansible_runner.run", return_value=mock_runner):
            result = check_claw_health("openclaw", mock_host)

    assert result["status"] == ClawStatus.STOPPED
    assert result["missing_secrets"] is None
