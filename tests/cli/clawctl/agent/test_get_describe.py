"""Tests for `clawctl agent get` and `clawctl agent describe`."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from clawrium.cli import app
from clawrium.cli.clawctl.agent._shared import _first_provider

runner = CliRunner()


def _patch_fleet_agent(fleet_dir, mutator) -> None:
    """Load hosts.json, apply mutator to the wise-hypatia agent record, save."""
    hosts_path = Path(fleet_dir) / "hosts.json"
    hosts = json.loads(hosts_path.read_text())
    mutator(hosts[0]["agents"]["openclaw"])
    hosts_path.write_text(json.dumps(hosts, indent=2))


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


# Stage status `status` primary read — B2 discriminating tests
# ---------------------------------------------------------------------------


def test_describe_stage_status_key_wins_over_state_key(fleet_dir) -> None:
    # B2: when both `status` and `state` are present, `status` must win.
    def mutate(agent):
        agent["onboarding"]["stages"]["providers"] = {
            "status": "complete",
            "state": "legacy-should-be-ignored",
        }

    _patch_fleet_agent(fleet_dir, mutate)

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    assert "legacy-should-be-ignored" not in onboarding_block
    providers_line = next(
        line for line in onboarding_block.splitlines() if "providers" in line
    )
    assert "complete" in providers_line


def test_describe_stage_status_only_no_state_fallback(fleet_dir) -> None:
    # W-B (iter-2): if `info.get("status")` is removed from describe.py,
    # this test fails — the `state` fallback returns None, default
    # "pending" wins, and the assertion below catches the regression.
    # Discriminates the primary-read failure mode without relying on
    # the two-key fixture or the empty-dict fixture (both of which
    # would silently pass with only the `state` fallback).
    def mutate(agent):
        agent["onboarding"]["stages"]["providers"] = {"status": "complete"}

    _patch_fleet_agent(fleet_dir, mutate)

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    providers_line = next(
        line for line in onboarding_block.splitlines() if "providers" in line
    )
    assert "complete" in providers_line
    assert "pending" not in providers_line


def test_describe_stage_missing_status_defaults_to_pending(fleet_dir) -> None:
    # B2: a stage record with neither `status` nor `state` falls back
    # to the default `pending`.
    def mutate(agent):
        agent["onboarding"]["stages"]["identity"] = {}

    _patch_fleet_agent(fleet_dir, mutate)

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    identity_line = next(
        line for line in onboarding_block.splitlines() if "identity" in line
    )
    assert "pending" in identity_line


# ---------------------------------------------------------------------------
# Backward-compatibility shim — `state`-key fallback for handwritten records
# ---------------------------------------------------------------------------


def test_describe_stage_state_key_fallback(fleet_dir) -> None:
    # W3 (iter-1): the `or info.get("state")` shim is kept for
    # handwritten / third-party records that use the old key shape.
    # Make it live and intentional by asserting it renders correctly
    # when only `state` is present. This is NOT a B2 discriminator —
    # see `test_describe_stage_status_only_no_state_fallback` for that.
    def mutate(agent):
        agent["onboarding"]["stages"]["validate"] = {"state": "complete"}

    _patch_fleet_agent(fleet_dir, mutate)

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    validate_line = next(
        line for line in onboarding_block.splitlines() if "validate" in line
    )
    assert "complete" in validate_line


# ---------------------------------------------------------------------------
# Provider column CLI-level coverage
# ---------------------------------------------------------------------------


def test_describe_provider_line_renders_attach_list_name(fleet_dir) -> None:
    # CLI-level coverage for the Provider column.
    def mutate(agent):
        agent["providers"] = ["clawrium-glm51"]

    _patch_fleet_agent(fleet_dir, mutate)

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    provider_line = next(
        line for line in result.output.splitlines() if line.startswith("Provider:")
    )
    assert "clawrium-glm51" in provider_line


# ---------------------------------------------------------------------------
# Tier-3 vestigial-list path safety (W-A iter-2)
# ---------------------------------------------------------------------------


def test_first_provider_tier3_list_dict_without_name_returns_none():
    # W-A: tier-3 list-of-dicts with a nameless entry. Used to fall
    # through `return first.get("name")` returning None; now explicit.
    record = {"config": {"providers": [{"type": "ollama"}]}}
    assert _first_provider(record) is None


def test_first_provider_tier3_list_none_entry_does_not_render_None_string():
    # W-A: `return str(first)` would have produced the literal string
    # "None" in the PROVIDER column. Must return None instead.
    record = {"config": {"providers": [None]}}
    assert _first_provider(record) is None


def test_first_provider_tier3_list_int_entry_does_not_coerce():
    # W-A: integer entry should not render as "42" in the PROVIDER
    # column.
    record = {"config": {"providers": [42]}}
    assert _first_provider(record) is None


# ---------------------------------------------------------------------------
# Type-safety on tier-1 dict `name` value (W-C iter-2)
# ---------------------------------------------------------------------------


def test_first_provider_dict_name_value_is_non_string_falls_through():
    # W-C: a dict attach-list entry whose `name` is itself a dict
    # would have rendered as a Python repr in the PROVIDER column.
    # Now falls through to the materialization tier.
    record = {
        "providers": [{"name": {"nested": "bad"}}],
        "config": {"provider": {"name": "clawrium-glm51"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


# ---------------------------------------------------------------------------
# Format validation on string entries (W-D iter-2 — defense-in-depth)
# ---------------------------------------------------------------------------


def test_first_provider_string_attach_with_markup_falls_through():
    # W-D: a handwritten attach entry containing Rich/markdown markup
    # (`[bold]x[/]`) does not match PROVIDER_NAME_PATTERN at write
    # time but historically passed the read-time check. Now read-time
    # also validates the pattern, falling through to the materialized
    # value so a malformed attach record cannot inject characters
    # into the PROVIDER column.
    record = {
        "providers": ["[bold]atk[/]"],
        "config": {"provider": {"name": "clawrium-glm51"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


def test_first_provider_string_attach_with_invalid_chars_falls_through():
    # W-D: pattern rejects names with `/`, `:`, etc. — falls through.
    record = {
        "providers": ["evil/path"],
        "config": {"provider": {"name": "clawrium-glm51"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


# ---------------------------------------------------------------------------
# Iter-3 cleanups (W-N-3, W-N-4, W-N-5)
# ---------------------------------------------------------------------------


def test_first_provider_tier3_list_dict_without_name_falls_through_to_tier2():
    # W-N-3 (iter-3): the existing "returns None" test was
    # non-discriminating (old code returned None for the same input).
    # This variant proves the dict-without-name in tier-3 list does
    # not short-circuit before tier-2 would otherwise resolve.
    record = {
        "config": {
            "providers": [{"type": "ollama"}],  # tier-3 dict, no name
            "provider": {"name": "tier2-fallback-name"},  # tier-2 wins
        },
    }
    # In _first_provider's iteration order, tier-2 is checked BEFORE
    # tier-3, so this actually exercises tier-2 winning. The point of
    # this test is that adding a malformed tier-3 entry doesn't break
    # the tier-2 read — i.e. _first_provider is robust to having
    # garbage in tiers it doesn't reach.
    assert _first_provider(record) == "tier2-fallback-name"


def test_first_provider_tier3_list_string_happy_path():
    # W-N-4: tier-3 list with a valid string entry. The post-W-A
    # rewrite uses `_accept` here; without a happy-path test, a
    # silent rejection (e.g. if PROVIDER_NAME_PATTERN were tightened)
    # would go uncaught.
    record = {"config": {"providers": ["valid-provider"]}}
    assert _first_provider(record) == "valid-provider"


def test_first_provider_tier3_list_dict_with_name_happy_path():
    # W-N-4: tier-3 list with a valid dict-with-name entry.
    record = {"config": {"providers": [{"name": "valid-provider"}]}}
    assert _first_provider(record) == "valid-provider"


def test_first_provider_accept_64_char_name_is_valid():
    # W-N-5: PROVIDER_NAME_PATTERN's `{0,63}` quantifier allows up to
    # 64 chars total (1 leading letter + 63 trailing). Exercise the
    # boundary so a future tightening (e.g. `{0,62}`) would be
    # caught by test failure rather than silent rejection at runtime.
    name_64 = "a" + "x" * 63
    assert len(name_64) == 64
    assert _first_provider({"providers": [name_64]}) == name_64


def test_first_provider_accept_65_char_name_falls_through():
    # W-N-5: one character over the limit must fall through.
    name_65 = "a" + "x" * 64
    assert len(name_65) == 65
    record = {
        "providers": [name_65],
        "config": {"provider": {"name": "clawrium-glm51"}},
    }
    assert _first_provider(record) == "clawrium-glm51"


def test_describe_stage_empty_status_string_does_not_use_state_shim(
    fleet_dir,
) -> None:
    # W-N-2: explicit `is not None` guard means `{"status": ""}`
    # renders "pending" (status key present, value empty) rather than
    # silently falling through to `state` (which would render
    # "complete"). Documents the intent the leader requested in
    # ATX iter-3.
    def mutate(agent):
        agent["onboarding"]["stages"]["validate"] = {
            "status": "",
            "state": "complete-from-state-shim",
        }

    _patch_fleet_agent(fleet_dir, mutate)

    result = runner.invoke(app, ["agent", "describe", "wise-hypatia"])
    assert result.exit_code == 0
    onboarding_block = result.output.split("Onboarding:", 1)[1]
    validate_line = next(
        line for line in onboarding_block.splitlines() if "validate" in line
    )
    # status key present but empty → renders pending, NOT state value
    assert "complete-from-state-shim" not in validate_line
    assert "pending" in validate_line
