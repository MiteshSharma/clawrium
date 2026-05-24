"""Tests for `clawctl agent sync` — dry-run path covers the streaming
contract without hitting `core/lifecycle.py:sync_agent` (which requires
a real SSH target). Bundle 5 wires the live wolf-i integration test.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_sync_dry_run_emits_5_phase_lines(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "sync", "wise-hypatia", "--dry-run"])
    assert result.exit_code == 0
    expected_phrases = [
        "validating local state",
        "pushing config",
        "restarting unit",
        "re-pairing gateway",
        "verifying health",
    ]
    for phrase in expected_phrases:
        assert phrase in result.output, f"missing phase line: {phrase}"
    assert "dry-run complete" in result.output


def test_sync_dry_run_json_emits_ndjson(fleet_dir) -> None:
    result = runner.invoke(
        app, ["agent", "sync", "wise-hypatia", "--dry-run", "-o", "json"]
    )
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line.strip()]
    # Each phase line is a JSON object; final state is appended too.
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
