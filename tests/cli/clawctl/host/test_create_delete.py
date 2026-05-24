"""Tests for `clawctl host create` and `clawctl host delete`.

These exercise the non-interactive contract: stdin-not-tty + missing
flag fails cleanly; stdin-not-tty + --yes proceeds.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_create_requires_user_on_non_tty(fleet_dir, stdin_not_tty) -> None:
    result = runner.invoke(app, ["host", "create", "192.168.1.100"])
    assert result.exit_code != 0
    assert "Error: missing required flag --user" in result.output


def test_create_with_user_succeeds(fleet_dir, stdin_not_tty) -> None:
    result = runner.invoke(
        app,
        ["host", "create", "192.168.1.100", "--user", "carol", "--alias", "newbox"],
    )
    assert result.exit_code == 0
    # New host appears in `host get`.
    result_list = runner.invoke(app, ["host", "get", "-o", "json"])
    parsed = json.loads(result_list.output)
    names = {row["name"] for row in parsed}
    assert "newbox" in names


def test_create_duplicate_same_settings_is_idempotent(fleet_dir, stdin_not_tty) -> None:
    runner.invoke(
        app, ["host", "create", "192.168.1.100", "--user", "carol", "--alias", "newbox"]
    )
    result = runner.invoke(
        app, ["host", "create", "192.168.1.100", "--user", "carol", "--alias", "newbox"]
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
    # Confirm it's gone.
    list_result = runner.invoke(app, ["host", "get", "-o", "name"])
    assert "host/kevin" not in list_result.output
