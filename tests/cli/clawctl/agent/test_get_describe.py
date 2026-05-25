"""Tests for `clawctl agent get` and `clawctl agent describe`."""

from __future__ import annotations

import json

import yaml
from typer.testing import CliRunner

from clawrium.cli import app
from clawrium.cli.clawctl.agent._shared import _first_provider

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


def test_describe_renders_completed_stage_status(fleet_dir) -> None:
    # Regression: describe.py read `info.get("state")` while stage records
    # are written by core/onboarding.py:complete_stage under `status`.
    # Every completed agent rendered every stage as "pending". The fixture
    # also had `state`, so no test caught the mismatch end-to-end until
    # both sides were aligned on the real key (`status`).
    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    assert "complete" in onboarding_block
    assert "skipped" in onboarding_block
    # Should NOT show pending for a stage that has a recorded status.
    # (Empty stages would still default to pending; the fixture has none.)
    pending_count = onboarding_block.lower().count("pending")
    assert pending_count == 0, (
        f"onboarding block reported {pending_count} pending stage(s) but "
        f"fixture has all stages with explicit status; block was:\n{onboarding_block}"
    )


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


# ---------------------------------------------------------------------------
# _first_provider read-order coverage
#
# Resolution order (see _shared.py:_first_provider docstring):
#   1. claw_record["providers"]                       # attach list (new)
#   2. claw_record["config"]["provider"]["name"]      # materialization layer
#   3. claw_record["config"]["providers"]             # vestigial plural
# ---------------------------------------------------------------------------


def test_first_provider_prefers_attach_list_string():
    record = {
        "providers": ["clawrium-glm51"],
        "config": {"provider": {"name": "ignored-stale-value"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


def test_first_provider_prefers_attach_list_dict_entry():
    record = {"providers": [{"name": "clawrium-glm51", "type": "openrouter"}]}
    assert _first_provider(record) == "clawrium-glm51"


def test_first_provider_falls_back_to_materialized_config_provider():
    # Covers every pre-Pattern-A install on disk: config.provider is the
    # singular dict written by sync_agent / configure_agent. Without this
    # fallback, `clawctl agent describe` showed `Provider: -` for every
    # legacy agent.
    record = {"config": {"provider": {"name": "clawrium-glm51"}}}
    assert _first_provider(record) == "clawrium-glm51"


def test_first_provider_skips_empty_attach_list_then_uses_materialization():
    record = {
        "providers": [],
        "config": {"provider": {"name": "clawrium-glm51"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


def test_first_provider_returns_none_when_nothing_present():
    assert _first_provider({}) is None
    assert _first_provider({"config": {}}) is None
    assert _first_provider({"config": {"provider": {}}}) is None


def test_first_provider_vestigial_plural_path_still_resolves():
    record = {"config": {"providers": {"legacy-name": {"type": "ollama"}}}}
    assert _first_provider(record) == "legacy-name"
