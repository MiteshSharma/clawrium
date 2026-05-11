"""Hermes onboarding pipeline tests (issue #68 Phase 4).

This module covers the Phase 4 contract for hermes onboarding: the manifest
declares a real pipeline (providers required, identity auto_skip, channels
required cli-only, validate composite), `can_skip_stage` honors per-stage
``auto_skip:true`` so the wizard skips identity without prompting, and
`validate_hermes_health` runs the three composite checks via Ansible on the
agent host.
"""

from unittest.mock import MagicMock, patch

import pytest

from clawrium.core.onboarding import can_skip_stage, get_stage_tasks
from clawrium.core.registry import load_manifest
from clawrium.core.validation import validate_hermes_health


# ---------------------------------------------------------------------------
# Manifest-level contracts.
# ---------------------------------------------------------------------------


def test_hermes_manifest_parses_with_real_onboarding_pipeline():
    """The hermes manifest validates under the existing registry schema and
    exposes the four canonical stages with the Phase 4 shape."""
    manifest = load_manifest("hermes")
    onboarding = manifest.get("onboarding") or {}
    stages = onboarding.get("stages") or {}
    assert set(stages.keys()) == {"providers", "identity", "channels", "validate"}


def test_hermes_providers_stage_is_required():
    manifest = load_manifest("hermes")
    providers = manifest["onboarding"]["stages"]["providers"]
    assert providers["required"] is True
    assert providers.get("auto_skip") is not True


def test_hermes_identity_stage_auto_skips():
    manifest = load_manifest("hermes")
    identity = manifest["onboarding"]["stages"]["identity"]
    assert identity["auto_skip"] is True
    assert identity["description"]


def test_hermes_channels_stage_default_cli():
    """channels stage is required and ships a confirm task whose default
    is the cli channel — there are no Discord/Slack/Telegram options in
    this iteration."""
    manifest = load_manifest("hermes")
    channels = manifest["onboarding"]["stages"]["channels"]
    assert channels["required"] is True

    tasks = channels.get("tasks", [])
    assert tasks, "hermes channels stage must declare at least one task"
    confirm_tasks = [t for t in tasks if t.get("type") == "confirm"]
    assert confirm_tasks
    assert confirm_tasks[0].get("default") is True


def test_hermes_validate_stage_runs_binary_env_health():
    manifest = load_manifest("hermes")
    validate_stage = manifest["onboarding"]["stages"]["validate"]
    tasks = validate_stage.get("tasks", [])
    task_ids = [t.get("id") for t in tasks]
    assert task_ids == ["binary_check", "env_check", "health_check"]


def test_hermes_stage_ordering_matches_canonical():
    manifest = load_manifest("hermes")
    stages = list(manifest["onboarding"]["stages"].keys())
    assert stages == ["providers", "identity", "channels", "validate"]


# ---------------------------------------------------------------------------
# can_skip_stage behavior — per-stage auto_skip:true must be honored.
# ---------------------------------------------------------------------------


def test_can_skip_stage_honors_hermes_identity_auto_skip():
    """Phase 4 contract: the configure wizard must skip identity for hermes
    without prompting, because hermes manages identity internally."""
    assert can_skip_stage("hermes", "identity") is True


def test_can_skip_stage_does_not_skip_required_stages():
    """providers/channels/validate are required for hermes — the wizard
    must run them."""
    assert can_skip_stage("hermes", "providers") is False
    assert can_skip_stage("hermes", "channels") is False
    assert can_skip_stage("hermes", "validate") is False


# ---------------------------------------------------------------------------
# get_stage_tasks plumbing.
# ---------------------------------------------------------------------------


def test_get_stage_tasks_returns_provider_select_and_test():
    tasks = get_stage_tasks("hermes", "providers")
    types = [t.get("type") for t in tasks]
    assert "provider_select" in types
    assert "provider_test" in types


# ---------------------------------------------------------------------------
# validate_hermes_health — three composite checks via Ansible.
# ---------------------------------------------------------------------------


@pytest.fixture
def hermes_host_record():
    return {
        "hostname": "192.168.1.36",
        "alias": "wolf-i",
        "user": "xclm",
        "port": 22,
        "key_id": "wolf-i",
        "agents": {
            "hermes-test": {
                "type": "hermes",
                "version": "2026.5.7",
                "agent_name": "hermes-test",
            }
        },
    }


def _build_mock_runner_result(stdout: str, rc: int = 0):
    event = {
        "event": "runner_on_ok",
        "event_data": {"res": {"stdout": stdout, "rc": rc}},
    }
    result = MagicMock()
    result.events = [event]
    return result


def test_validate_hermes_health_passes_when_all_checks_succeed(hermes_host_record):
    stdout = "BINARY_CHECK\nv0.13.0 (2026.5.7)\nBINARY_RC=0\nENV_CHECK\nENV_OK\nHEALTH_CHECK\n200\n"

    with (
        patch(
            "clawrium.core.validation.get_host",
            return_value=hermes_host_record,
        ),
        patch(
            "clawrium.core.keys.get_host_private_key",
            return_value="/tmp/fake-key",
        ),
        patch(
            "ansible_runner.run",
            return_value=_build_mock_runner_result(stdout),
        ),
    ):
        result = validate_hermes_health("wolf-i", "hermes-test")

    assert result.passed is True
    assert result.errors == []
    assert result.details["health_status"] == "200"
    assert result.details["binary_rc"] == 0
    assert result.details["env_ok"] is True


def test_validate_hermes_health_fails_when_health_not_200(hermes_host_record):
    stdout = (
        "BINARY_CHECK\nv0.13.0 (2026.5.7)\nBINARY_RC=0\n"
        "ENV_CHECK\nENV_OK\n"
        "HEALTH_CHECK\nCURL_FAILED\n"
    )

    with (
        patch(
            "clawrium.core.validation.get_host",
            return_value=hermes_host_record,
        ),
        patch(
            "clawrium.core.keys.get_host_private_key",
            return_value="/tmp/fake-key",
        ),
        patch(
            "ansible_runner.run",
            return_value=_build_mock_runner_result(stdout),
        ),
    ):
        result = validate_hermes_health("wolf-i", "hermes-test")

    assert result.passed is False
    assert any("/health" in e for e in result.errors)


def test_validate_hermes_health_fails_when_env_missing(hermes_host_record):
    stdout = (
        "BINARY_CHECK\nv0.13.0 (2026.5.7)\nBINARY_RC=0\n"
        "ENV_CHECK\nENV_MISSING\n"
        "HEALTH_CHECK\n200\n"
    )

    with (
        patch(
            "clawrium.core.validation.get_host",
            return_value=hermes_host_record,
        ),
        patch(
            "clawrium.core.keys.get_host_private_key",
            return_value="/tmp/fake-key",
        ),
        patch(
            "ansible_runner.run",
            return_value=_build_mock_runner_result(stdout),
        ),
    ):
        result = validate_hermes_health("wolf-i", "hermes-test")

    assert result.passed is False
    assert any(".env" in e for e in result.errors)


def test_validate_hermes_health_fails_when_binary_missing(hermes_host_record):
    stdout = (
        "BINARY_CHECK\nhermes: command not found\nBINARY_RC=127\n"
        "ENV_CHECK\nENV_OK\n"
        "HEALTH_CHECK\n200\n"
    )

    with (
        patch(
            "clawrium.core.validation.get_host",
            return_value=hermes_host_record,
        ),
        patch(
            "clawrium.core.keys.get_host_private_key",
            return_value="/tmp/fake-key",
        ),
        patch(
            "ansible_runner.run",
            return_value=_build_mock_runner_result(stdout, rc=127),
        ),
    ):
        result = validate_hermes_health("wolf-i", "hermes-test")

    assert result.passed is False
    assert any("hermes" in e.lower() for e in result.errors)


def test_validate_hermes_health_reports_missing_agent(hermes_host_record):
    """If the agent record is absent on the host, validate_hermes_health must
    return a clean ValidationResult rather than dispatching Ansible."""
    host_without_agent = {**hermes_host_record, "agents": {}}

    with patch(
        "clawrium.core.validation.get_host",
        return_value=host_without_agent,
    ):
        result = validate_hermes_health("wolf-i", "hermes-test")

    assert result.passed is False
    assert any("not" in e.lower() for e in result.errors)
