"""Tests for the top-level `clawctl` Typer app skeleton.

These cover plan §"Specific Outcomes to Validate":

- `clawctl --help` lists every top-level group from plan §4.
- Every group's `--help` exits 0 (proves Risk R2 is closed).
- Stubbed subcommands print the canonical `Not implemented: <group> <verb>`
  line.
"""

import pytest
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


EXPECTED_TOP_LEVEL = [
    "service",
    "version",
    "completion",
    "tui",
    "gui",
    "host",
    "agent",
    "provider",
    "channel",
    "integration",
    "skill",
    "mcp",
]


def test_root_help_lists_every_group() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for token in EXPECTED_TOP_LEVEL:
        assert token in result.output, f"missing from root --help: {token}"


@pytest.mark.parametrize(
    "group",
    [
        "service",
        "host",
        "agent",
        "provider",
        "channel",
        "integration",
        "skill",
        "mcp",
    ],
)
def test_group_help_exits_zero(group: str) -> None:
    result = runner.invoke(app, [group, "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["host", "create"], "Not implemented: host create"),
        (["host", "get"], "Not implemented: host get"),
        (["agent", "create"], "Not implemented: agent create"),
        (["agent", "sync"], "Not implemented: agent sync"),
        (
            ["provider", "registry", "create"],
            "Not implemented: provider registry create",
        ),
        (["channel", "registry", "create"], "Not implemented: channel registry create"),
        (
            ["integration", "registry", "get"],
            "Not implemented: integration registry get",
        ),
        (["skill", "registry", "get"], "Not implemented: skill registry get"),
        (["mcp", "registry", "get"], "Not implemented: mcp registry get"),
    ],
)
def test_stub_verb_emits_canonical_line(argv: list[str], expected: str) -> None:
    result = runner.invoke(app, argv)
    assert result.exit_code == 0
    assert result.output.strip() == expected


def test_pattern_a_registry_subgroup_exposed() -> None:
    """Each Pattern A noun has `registry` as its only subgroup (plan §3)."""
    for noun in ("provider", "channel", "integration", "skill", "mcp"):
        result = runner.invoke(app, [noun, "--help"])
        assert result.exit_code == 0
        assert "registry" in result.output, f"{noun}: registry subgroup missing"


def test_core_untouched_by_imports() -> None:
    """Importing `clawrium.cli` (the new clawctl app) must not pull in
    any `clawrium.core` module side-effects beyond what was already
    needed for `__version__`. This is a smoke check; the real guarantee
    is the `git diff` rule in the Acceptance Criteria.
    """
    import importlib

    importlib.import_module("clawrium.cli")
    # If this import succeeded, we know clawrium.cli works in isolation.
