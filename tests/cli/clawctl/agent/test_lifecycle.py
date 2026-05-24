"""Tests for `clawctl agent start|stop|restart` (ATX iter-1 B5).

Covers: unknown agent error path, `LifecycleError` propagation, and
the `result.get('success')` guard. Mocks `core/lifecycle.py` so no
real Ansible / SSH is invoked.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


@pytest.mark.parametrize("verb", ["start", "stop", "restart"])
def test_unknown_agent_errors(fleet_dir, verb: str) -> None:
    result = runner.invoke(app, ["agent", verb, "no-such-agent"])
    assert result.exit_code != 0
    assert "not found" in result.output


@pytest.mark.parametrize(
    "verb,mock_target",
    [
        ("start", "clawrium.cli.clawctl.agent.start.start_agent"),
        ("stop", "clawrium.cli.clawctl.agent.stop.stop_agent"),
        ("restart", "clawrium.cli.clawctl.agent.restart.restart_agent"),
    ],
)
def test_lifecycle_error_exits_nonzero(
    fleet_dir, monkeypatch, verb: str, mock_target: str
) -> None:
    from clawrium.core.lifecycle import LifecycleError

    def boom(**_kwargs):
        raise LifecycleError("simulated failure")

    monkeypatch.setattr(mock_target, boom)
    result = runner.invoke(app, ["agent", verb, "wise-hypatia"])
    assert result.exit_code != 0
    assert "failed" in result.output


@pytest.mark.parametrize(
    "verb,mock_target",
    [
        ("start", "clawrium.cli.clawctl.agent.start.start_agent"),
        ("stop", "clawrium.cli.clawctl.agent.stop.stop_agent"),
        ("restart", "clawrium.cli.clawctl.agent.restart.restart_agent"),
    ],
)
def test_success_false_exits_nonzero(
    fleet_dir, monkeypatch, verb: str, mock_target: str
) -> None:
    def returns_failure(**_kwargs):
        return {"success": False, "error": "remote unit down"}

    monkeypatch.setattr(mock_target, returns_failure)
    result = runner.invoke(app, ["agent", verb, "wise-hypatia"])
    assert result.exit_code != 0
    assert "remote unit down" in result.output


@pytest.mark.parametrize(
    "verb,mock_target,past_tense",
    [
        ("start", "clawrium.cli.clawctl.agent.start.start_agent", "started"),
        ("stop", "clawrium.cli.clawctl.agent.stop.stop_agent", "stopped"),
        ("restart", "clawrium.cli.clawctl.agent.restart.restart_agent", "restarted"),
    ],
)
def test_success_path_emits_past_tense_line(
    fleet_dir, monkeypatch, verb: str, mock_target: str, past_tense: str
) -> None:
    def returns_success(**_kwargs):
        return {"success": True}

    monkeypatch.setattr(mock_target, returns_success)
    result = runner.invoke(app, ["agent", verb, "wise-hypatia"])
    assert result.exit_code == 0
    assert past_tense in result.output
