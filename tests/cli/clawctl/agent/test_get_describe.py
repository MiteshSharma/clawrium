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


def test_first_provider_dict_entry_without_name_falls_through_to_materialization():
    # ATX W1: a dict attach-list entry that's missing the `name` key
    # must NOT short-circuit the function with None. It must fall
    # through to the config.provider.name materialization tier so a
    # malformed attach record doesn't silently swallow the real value.
    record = {
        "providers": [{"type": "openrouter"}],  # no `name`
        "config": {"provider": {"name": "clawrium-glm51"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


def test_first_provider_empty_string_attach_entry_falls_through():
    # Defence-in-depth: empty string in attach list should not render
    # as the provider name; fall through to materialization.
    record = {
        "providers": [""],
        "config": {"provider": {"name": "clawrium-glm51"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


def test_first_provider_never_synced_agent_shape():
    # Matches the shape install.py writes before any sync runs:
    # `{"config": {"gateway": {...}}}` — no `provider` key at all.
    # _first_provider must return None (renders as `-`) without
    # raising.
    record = {"config": {"gateway": {"url": "http://localhost:40000"}}}
    assert _first_provider(record) is None


# ---------------------------------------------------------------------------
# Onboarding stage status rendering (B2 + W3 coverage)
# ---------------------------------------------------------------------------


def test_describe_stage_status_key_wins_over_state_key(
    fleet_dir, monkeypatch
) -> None:
    # B2: when both `status` and `state` are present, `status` must win.
    # The fixture's wise-hypatia agent gets a stage that carries both
    # keys; the rendered output should contain the `status` value, not
    # the `state` value.
    import json
    from pathlib import Path

    hosts_path = Path(fleet_dir) / "hosts.json"
    hosts = json.loads(hosts_path.read_text())
    hosts[0]["agents"]["openclaw"]["onboarding"]["stages"]["providers"] = {
        "status": "complete",
        "state": "legacy-should-be-ignored",
    }
    hosts_path.write_text(json.dumps(hosts, indent=2))

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    assert "legacy-should-be-ignored" not in onboarding_block
    # The providers line should render the status value.
    providers_line = next(
        line for line in onboarding_block.splitlines() if "providers" in line
    )
    assert "complete" in providers_line


def test_describe_stage_state_key_fallback(fleet_dir) -> None:
    # W3: the `or info.get("state")` shim is kept for handwritten /
    # third-party records that use the old key shape. Make it live and
    # intentional by asserting it renders correctly when only `state`
    # is present.
    import json
    from pathlib import Path

    hosts_path = Path(fleet_dir) / "hosts.json"
    hosts = json.loads(hosts_path.read_text())
    hosts[0]["agents"]["openclaw"]["onboarding"]["stages"]["validate"] = {
        "state": "complete",  # only `state`, no `status`
    }
    hosts_path.write_text(json.dumps(hosts, indent=2))

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    validate_line = next(
        line for line in onboarding_block.splitlines() if "validate" in line
    )
    assert "complete" in validate_line


def test_describe_stage_missing_status_defaults_to_pending(
    fleet_dir,
) -> None:
    # B2: a stage record with neither `status` nor `state` falls back
    # to the default `pending`.
    import json
    from pathlib import Path

    hosts_path = Path(fleet_dir) / "hosts.json"
    hosts = json.loads(hosts_path.read_text())
    hosts[0]["agents"]["openclaw"]["onboarding"]["stages"]["identity"] = {}
    hosts_path.write_text(json.dumps(hosts, indent=2))

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    identity_line = next(
        line for line in onboarding_block.splitlines() if "identity" in line
    )
    assert "pending" in identity_line


def test_describe_provider_line_renders_attach_list_name(fleet_dir) -> None:
    # CLI-level coverage for the Provider column: previously only the
    # unit-level _first_provider tests asserted the read-order chain.
    # The fixture's wise-hypatia agent gets a provider attached; the
    # rendered output must contain that name on the Provider line.
    import json
    from pathlib import Path

    hosts_path = Path(fleet_dir) / "hosts.json"
    hosts = json.loads(hosts_path.read_text())
    hosts[0]["agents"]["openclaw"]["providers"] = ["clawrium-glm51"]
    hosts_path.write_text(json.dumps(hosts, indent=2))

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    provider_line = next(
        line for line in result.output.splitlines() if line.startswith("Provider:")
    )
    assert "clawrium-glm51" in provider_line
