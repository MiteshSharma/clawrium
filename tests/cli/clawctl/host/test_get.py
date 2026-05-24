"""Tests for `clawctl host get` — output formats + selector + non-interactive."""

from __future__ import annotations

import json

import yaml
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_default_table_lists_seeded_hosts(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "get"])
    assert result.exit_code == 0
    assert "NAME" in result.output
    assert "wolf-i" in result.output
    assert "kevin" in result.output


def test_no_headers_suppresses_header_row(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "get", "--no-headers"])
    assert result.exit_code == 0
    assert "NAME" not in result.output
    assert "wolf-i" in result.output


def test_output_json_is_parseable_array(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "get", "-o", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert all(row["kind"] == "host" for row in parsed)
    assert {row["name"] for row in parsed} == {"wolf-i", "kevin"}


def test_output_yaml_round_trips_with_json(fleet_dir) -> None:
    json_out = runner.invoke(app, ["host", "get", "-o", "json"])
    yaml_out = runner.invoke(app, ["host", "get", "-o", "yaml"])
    assert json_out.exit_code == 0
    assert yaml_out.exit_code == 0
    assert json.loads(json_out.output) == yaml.safe_load(yaml_out.output)


def test_output_name_emits_kind_slash_name(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "get", "-o", "name"])
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line]
    assert lines == ["host/wolf-i", "host/kevin"]


def test_output_wide_includes_extra_columns(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "get", "-o", "wide"])
    assert result.exit_code == 0
    assert "PORT" in result.output
    assert "LABELS" in result.output


def test_selector_filters_by_label(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "get", "-l", "env=prod"])
    assert result.exit_code == 0
    assert "wolf-i" in result.output
    assert "kevin" not in result.output


def test_invalid_selector_fails_with_hint(fleet_dir) -> None:
    result = runner.invoke(app, ["host", "get", "-l", "noequals"])
    assert result.exit_code != 0
    assert "Error: invalid selector" in result.output
