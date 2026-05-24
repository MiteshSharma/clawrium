"""Tests for `-o json`, `-o yaml`, `-o name` serializers."""

import json

import yaml

from clawrium.cli.output.json_yaml import dump_json, dump_name, dump_yaml


SAMPLE_ROWS = [
    {
        "kind": "agent",
        "name": "wise-hypatia",
        "type": "openclaw",
        "host": "wolf-i",
        "status": "running",
        "age_seconds": 259200,
        "installed_at": "2026-05-20T14:23:11Z",
    },
    {
        "kind": "agent",
        "name": "hermes-prod",
        "type": "hermes",
        "host": "kevin",
        "status": "running",
        "age_seconds": 86400,
        "installed_at": "2026-05-22T09:00:00Z",
    },
]


class TestDumpJson:
    def test_parses_as_json_array(self) -> None:
        out = dump_json(SAMPLE_ROWS)
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_snake_case_keys(self) -> None:
        out = dump_json(SAMPLE_ROWS)
        parsed = json.loads(out)
        for row in parsed:
            for key in row:
                assert "_" in key or key.islower(), f"non-snake_case key: {key}"

    def test_age_seconds_is_int(self) -> None:
        out = dump_json(SAMPLE_ROWS)
        parsed = json.loads(out)
        for row in parsed:
            assert isinstance(row["age_seconds"], int)

    def test_ends_with_newline(self) -> None:
        out = dump_json(SAMPLE_ROWS)
        assert out.endswith("\n")


class TestDumpYaml:
    def test_yaml_equivalent_to_json(self) -> None:
        out_yaml = dump_yaml(SAMPLE_ROWS)
        out_json = dump_json(SAMPLE_ROWS)
        assert yaml.safe_load(out_yaml) == json.loads(out_json)

    def test_yaml_is_block_style(self) -> None:
        out = dump_yaml(SAMPLE_ROWS)
        # block style uses `- ` for list items and `key:` per line
        assert "- kind:" in out or "- name:" in out or "- " in out


class TestDumpName:
    def test_one_per_line(self) -> None:
        out = dump_name(SAMPLE_ROWS)
        lines = out.strip().split("\n")
        assert lines == ["agent/wise-hypatia", "agent/hermes-prod"]

    def test_no_header(self) -> None:
        out = dump_name(SAMPLE_ROWS)
        assert "KIND" not in out
        assert "NAME" not in out

    def test_no_padding(self) -> None:
        out = dump_name(SAMPLE_ROWS)
        for line in out.strip().split("\n"):
            assert line == line.strip()

    def test_empty_input(self) -> None:
        assert dump_name([]) == ""
