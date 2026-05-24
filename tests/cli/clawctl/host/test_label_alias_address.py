"""Tests for `clawctl host label`, `host alias`, and `host address`."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_label_set_and_remove(fleet_dir) -> None:
    set_result = runner.invoke(app, ["host", "label", "wolf-i", "role=web", "tier=a"])
    assert set_result.exit_code == 0
    describe = runner.invoke(app, ["host", "describe", "wolf-i", "-o", "json"])
    labels = json.loads(describe.output)[0]["labels"]
    assert labels.get("role") == "web"
    assert labels.get("tier") == "a"

    remove_result = runner.invoke(app, ["host", "label", "wolf-i", "role-"])
    assert remove_result.exit_code == 0
    describe2 = runner.invoke(app, ["host", "describe", "wolf-i", "-o", "json"])
    labels2 = json.loads(describe2.output)[0]["labels"]
    assert "role" not in labels2
    assert labels2.get("tier") == "a"


def test_alias_add_remove_list(fleet_dir) -> None:
    add_result = runner.invoke(
        app, ["host", "alias", "wolf-i", "--add", "wolfie", "--add", "primary"]
    )
    assert add_result.exit_code == 0

    list_result = runner.invoke(app, ["host", "alias", "wolf-i", "--list"])
    assert list_result.exit_code == 0
    assert "wolf-i" in list_result.output
    assert "wolfie" in list_result.output
    assert "primary" in list_result.output

    remove_result = runner.invoke(
        app, ["host", "alias", "wolf-i", "--remove", "wolfie"]
    )
    assert remove_result.exit_code == 0
    list_after = runner.invoke(app, ["host", "alias", "wolf-i", "--list"])
    assert "wolfie" not in list_after.output


def test_address_add_get_set_primary_delete(fleet_dir) -> None:
    add_result = runner.invoke(
        app, ["host", "address", "add", "wolf-i", "10.0.0.99", "--label", "alt"]
    )
    assert add_result.exit_code == 0

    get_result = runner.invoke(app, ["host", "address", "get", "wolf-i"])
    assert "10.0.0.99" in get_result.output

    set_result = runner.invoke(
        app, ["host", "address", "set-primary", "wolf-i", "10.0.0.99"]
    )
    assert set_result.exit_code == 0

    del_result = runner.invoke(app, ["host", "address", "delete", "wolf-i", "10.0.0.1"])
    assert del_result.exit_code == 0
