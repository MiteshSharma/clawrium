"""Tests for `clawctl host reset` (ATX iter-1 B9)."""

from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_reset_non_tty_without_yes_fails(fleet_dir, stdin_not_tty, monkeypatch) -> None:
    targets = SimpleNamespace(users=[], services=[], paths=[])
    monkeypatch.setattr(
        "clawrium.cli.clawctl.host.reset.enumerate_targets", lambda _h: targets
    )
    result = runner.invoke(app, ["host", "reset", "wolf-i"])
    assert result.exit_code != 0
    assert "--yes" in result.output


def test_reset_dry_run_lists_targets(fleet_dir, monkeypatch) -> None:
    targets = SimpleNamespace(
        users=["u1"], services=["svc1.service"], paths=["/var/lib/foo"]
    )
    called = []
    monkeypatch.setattr(
        "clawrium.cli.clawctl.host.reset.enumerate_targets", lambda _h: targets
    )
    monkeypatch.setattr(
        "clawrium.cli.clawctl.host.reset.execute_reset",
        lambda *a, **k: called.append((a, k)),
    )
    result = runner.invoke(app, ["host", "reset", "wolf-i", "--dry-run"])
    assert result.exit_code == 0
    assert "would remove" in result.output
    assert called == []  # execute_reset MUST NOT be called on dry-run


def test_reset_unknown_host_errors(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "reset", "no-such-host", "--yes"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_reset_yes_calls_execute(fleet_dir, monkeypatch) -> None:
    targets = SimpleNamespace(users=[], services=[], paths=[])
    result_obj = SimpleNamespace(
        success=True, removed={"users": 0, "services": 0, "paths": 0}, errors=[]
    )
    monkeypatch.setattr(
        "clawrium.cli.clawctl.host.reset.enumerate_targets", lambda _h: targets
    )
    monkeypatch.setattr(
        "clawrium.cli.clawctl.host.reset.execute_reset",
        lambda _h, _t: result_obj,
    )
    result = runner.invoke(app, ["host", "reset", "wolf-i", "--yes"])
    assert result.exit_code == 0
    assert "reset complete" in result.output
