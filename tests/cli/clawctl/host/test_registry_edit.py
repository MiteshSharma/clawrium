"""Tests for `clawctl host registry` and `clawctl host edit`."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_registry_get_lists_profiles(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "registry", "get"])
    assert result.exit_code == 0
    assert "generic-ssh" in result.output


def test_registry_describe_known_profile(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "registry", "describe", "generic-ssh"])
    assert result.exit_code == 0
    assert "Name:" in result.output


def test_registry_describe_unknown_profile_exits_nonzero(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "registry", "describe", "no-such-profile"])
    assert result.exit_code != 0


def test_edit_updates_user(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "edit", "wolf-i", "--user", "carol"])
    assert result.exit_code == 0
    describe = runner.invoke(app, ["host", "describe", "wolf-i", "-o", "json"])
    assert json.loads(describe.output)[0]["user"] == "carol"


def test_edit_no_flags_errors(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "edit", "wolf-i"])
    assert result.exit_code != 0
    assert "Error:" in result.output
