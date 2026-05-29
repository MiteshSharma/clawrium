"""Tests for `clawctl host create` and `clawctl host delete`.

These exercise:
  - The non-interactive contract (stdin-not-tty + missing flag fails;
    stdin-not-tty + --yes proceeds for delete).
  - The `--user xclm` requirement.
  - The two-phase create flow: first run generates a keypair and prints
    manual setup commands when xclm SSH fails; re-run after manual setup
    succeeds and persists the host record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


@pytest.fixture
def mock_ssh_fail(monkeypatch):
    """Force `clawctl host create` to see xclm SSH verification fail."""
    monkeypatch.setattr(
        "clawrium.cli.clawctl.host.create.test_ssh_connection",
        lambda **_kw: (False, "Authentication failed - check SSH keys"),
    )


@pytest.fixture
def mock_ssh_ok(monkeypatch):
    """Force `clawctl host create` to see xclm SSH verification succeed."""
    monkeypatch.setattr(
        "clawrium.cli.clawctl.host.create.test_ssh_connection",
        lambda **_kw: (True, "Connection successful"),
    )


def test_create_requires_user_on_non_tty(fleet_dir, stdin_not_tty) -> None:
    result = runner.invoke(app, ["host", "create", "192.168.1.100"])
    assert result.exit_code != 0
    assert "Error: missing required flag --user" in result.output


def test_create_rejects_non_xclm_user(fleet_dir, stdin_not_tty) -> None:
    result = runner.invoke(
        app,
        ["host", "create", "192.168.1.100", "--user", "carol", "--alias", "newbox"],
    )
    assert result.exit_code != 0
    assert "must be 'xclm'" in result.output


def test_create_first_run_generates_keypair_and_prints_manual_setup(
    fleet_dir, stdin_not_tty, mock_ssh_fail
) -> None:
    result = runner.invoke(
        app,
        ["host", "create", "192.168.1.100", "--user", "xclm", "--alias", "newbox"],
    )
    assert result.exit_code == 1, result.output
    # Keypair was generated under the XDG config dir.
    key_dir: Path = fleet_dir / "keys" / "192.168.1.100"
    assert (key_dir / "xclm_ed25519").exists()
    assert (key_dir / "xclm_ed25519.pub").exists()
    # Both OS blocks are present, with the macOS-only access_ssh hint.
    assert "## Linux" in result.output
    assert "## macOS" in result.output
    assert "com.apple.access_ssh" in result.output
    assert "ssh-ed25519" in result.output
    # Host record was NOT persisted on this run.
    list_result = runner.invoke(app, ["host", "get", "-o", "json"])
    parsed = json.loads(list_result.output)
    assert all(row["name"] != "newbox" for row in parsed)


def test_create_rerun_after_manual_setup_succeeds(
    fleet_dir, stdin_not_tty, mock_ssh_fail
) -> None:
    # Run 1: surfaces manual commands, generates keypair, exits non-zero.
    first = runner.invoke(
        app,
        ["host", "create", "192.168.1.100", "--user", "xclm", "--alias", "newbox"],
    )
    assert first.exit_code == 1

    # Run 2: pretend the operator pasted the commands and xclm is now reachable.
    # Swap the SSH stub from fail to ok via a fresh monkeypatch.
    import clawrium.cli.clawctl.host.create as create_mod

    create_mod.test_ssh_connection = lambda **_kw: (True, "Connection successful")

    second = runner.invoke(
        app,
        ["host", "create", "192.168.1.100", "--user", "xclm", "--alias", "newbox"],
    )
    assert second.exit_code == 0, second.output

    list_result = runner.invoke(app, ["host", "get", "-o", "json"])
    parsed = json.loads(list_result.output)
    names = {row["name"] for row in parsed}
    assert "newbox" in names


def test_create_idempotent_when_record_already_matches(
    fleet_dir, stdin_not_tty, mock_ssh_ok
) -> None:
    runner.invoke(
        app, ["host", "create", "192.168.1.100", "--user", "xclm", "--alias", "newbox"]
    )
    result = runner.invoke(
        app, ["host", "create", "192.168.1.100", "--user", "xclm", "--alias", "newbox"]
    )
    assert result.exit_code == 0
    assert "already exists" in result.output


def test_delete_non_tty_without_yes_fails(fleet_dir, stdin_not_tty) -> None:
    result = runner.invoke(app, ["host", "delete", "kevin"])
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "--yes" in result.output


def test_delete_non_tty_with_yes_succeeds(fleet_dir, stdin_not_tty) -> None:
    result = runner.invoke(app, ["host", "delete", "kevin", "--yes"])
    assert result.exit_code == 0
    list_result = runner.invoke(app, ["host", "get", "-o", "name"])
    assert "host/kevin" not in list_result.output
