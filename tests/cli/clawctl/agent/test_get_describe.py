"""Tests for `clawctl agent get` and `clawctl agent describe`."""

from __future__ import annotations

import json

import yaml
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_get_default_columns(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "get"])
    assert result.exit_code == 0
    for col in ("NAME", "TYPE", "HOST", "PROVIDER", "STATUS", "AGE"):
        assert col in result.output, f"missing column: {col}"
    assert "wise-hypatia" in result.output


def test_get_wide_includes_extra_columns(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "get", "-o", "wide"])
    assert result.exit_code == 0
    for col in ("ADDRESS", "PORT", "VERSION", "INSTALLED"):
        assert col in result.output, f"missing wide column: {col}"


def test_get_json_round_trip_yaml(fleet_dir) -> None:
    json_out = runner.invoke(app, ["agent", "get", "-o", "json"])
    yaml_out = runner.invoke(app, ["agent", "get", "-o", "yaml"])
    assert json_out.exit_code == 0
    assert yaml_out.exit_code == 0
    assert json.loads(json_out.output) == yaml.safe_load(yaml_out.output)


def test_get_name_format(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "get", "-o", "name"])
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert lines == ["agent/wise-hypatia"]


def test_get_selector_filters_via_host_labels(fleet_dir) -> None:
    # `kevin` (env=dev) has no agents, `wolf-i` (env=prod) has one.
    prod = runner.invoke(app, ["agent", "get", "-l", "env=prod", "-o", "name"])
    dev = runner.invoke(app, ["agent", "get", "-l", "env=dev", "-o", "name"])
    assert "agent/wise-hypatia" in prod.output
    assert "agent/wise-hypatia" not in dev.output


def test_describe_includes_onboarding(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    assert "Onboarding:" in result.output
    assert "providers" in result.output
    assert "validate" in result.output


def test_describe_unknown_agent_errors(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "describe", "nope"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_describe_json(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "describe", "wise-hypatia", "-o", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed[0]["name"] == "wise-hypatia"
    assert parsed[0]["kind"] == "agent"
