"""Tests for `clawctl agent sync` — dry-run path covers the streaming
contract without hitting the canonical pipeline (which requires a real
SSH target). Bundle 5 wires the live wolf-i integration test.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_sync_dry_run_emits_phase_lines(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia", "--dry-run"])
    assert result.exit_code == 0
    expected_phrases = [
        "validating local state",
        "pushing config",
        "restarting unit",
        "verifying health",
    ]
    for phrase in expected_phrases:
        assert phrase in result.output, f"missing phase line: {phrase}"
    # #560: canonical pipeline does not re-pair the gateway; that phase
    # is intentionally absent from the post-#560 contract.
    assert "re-pairing gateway" not in result.output
    assert "dry-run complete" in result.output


def test_sync_dry_run_json_emits_ndjson(fleet_dir) -> None:
    result = runner.invoke(
        app, ["agent", "sync", "wise-hypatia", "--dry-run", "-o", "json"]
    )
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line.strip()]
    parsed = [json.loads(line) for line in lines]
    for event in parsed:
        assert event["resource"] == "agent/wise-hypatia"
        assert "phase" in event
        assert "state" in event


def test_sync_skip_validate_drops_phase_1(fleet_dir) -> None:
    result = runner.invoke(
        app, ["agent", "sync", "wise-hypatia", "--dry-run", "--skip-validate"]
    )
    assert result.exit_code == 0
    assert "validating local state" not in result.output
    assert "pushing config" in result.output


def test_sync_workspace_skips_restart(fleet_dir) -> None:
    result = runner.invoke(
        app, ["agent", "sync", "wise-hypatia", "--dry-run", "--workspace"]
    )
    assert result.exit_code == 0
    assert "restarting unit" not in result.output


# ---------------------------------------------------------------------------
# #560 regression guards: --canonical was dropped; re-introduction as a no-op
# should be caught.
# ---------------------------------------------------------------------------


def test_sync_rejects_removed_canonical_flag(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia", "--canonical"])
    assert result.exit_code != 0
    assert "--canonical" in result.output


# ---------------------------------------------------------------------------
# #560 B5: error-path coverage for the only sync pipeline.
#
# `result.output` from CliRunner is the mixed stdout+stderr stream
# (Click 8.2+); `emit_error()` writes to stderr but content lands here.
# ---------------------------------------------------------------------------


def _patch_canonical(monkeypatch, exc) -> None:
    def _raise(*args, **kwargs):
        raise exc

    monkeypatch.setattr(
        "clawrium.core.lifecycle_canonical.sync_agent_canonical", _raise
    )


class _StubResult:
    files_written: list[str] = []
    files_unchanged: list[str] = []


def _patch_canonical_capture(monkeypatch) -> dict:
    captured: dict = {}

    def _cap(name, **kwargs):
        captured["name"] = name
        captured.update(kwargs)
        return _StubResult()

    monkeypatch.setattr(
        "clawrium.core.lifecycle_canonical.sync_agent_canonical", _cap
    )
    return captured


def test_sync_force_flag_forwarded_to_canonical(fleet_dir, monkeypatch) -> None:
    captured = _patch_canonical_capture(monkeypatch)
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia", "--force"])
    assert result.exit_code == 0, result.output
    assert captured.get("force") is True


def test_sync_workspace_flag_disables_restart_and_verify(
    fleet_dir, monkeypatch
) -> None:
    captured = _patch_canonical_capture(monkeypatch)
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia", "--workspace"])
    assert result.exit_code == 0, result.output
    assert captured.get("restart") is False
    assert captured.get("verify") is False


def test_sync_surfaces_secret_removal_refused(fleet_dir, monkeypatch) -> None:
    from clawrium.core.lifecycle_canonical import SecretRemovalRefused

    _patch_canonical(
        monkeypatch,
        SecretRemovalRefused(
            "refusing to sync 'wise-hypatia': rendered body removes "
            "host-side secrets (.zeroclaw/config.toml: would remove "
            "['DISCORD_BOT_TOKEN']). Re-run with `--force` if intentional."
        ),
    )
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia"])
    assert result.exit_code != 0
    assert "refusing to sync" in result.output
    assert "--force" in result.output


def test_sync_surfaces_canonical_sync_error(fleet_dir, monkeypatch) -> None:
    from clawrium.core.lifecycle_canonical import CanonicalSyncError

    _patch_canonical(monkeypatch, CanonicalSyncError("ssh probe failed"))
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia"])
    assert result.exit_code != 0
    assert "sync failed" in result.output
    assert "ssh probe failed" in result.output


def test_sync_surfaces_remote_read_error(fleet_dir, monkeypatch) -> None:
    from clawrium.core.render_diff import RemoteReadError

    _patch_canonical(monkeypatch, RemoteReadError("connection refused"))
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia"])
    assert result.exit_code != 0
    assert "sync failed" in result.output
    assert "connection refused" in result.output


def test_sync_surfaces_agent_config_error(fleet_dir, monkeypatch) -> None:
    from clawrium.core.render import AgentConfigError

    _patch_canonical(monkeypatch, AgentConfigError("no provider attached"))
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia"])
    assert result.exit_code != 0
    assert "sync failed" in result.output
    assert "no provider attached" in result.output
