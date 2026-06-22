"""Tests for `clawctl agent audit <name>` — issue #780.

The agent-scoped surface is a single read-only command: a thin
facade over the top-level audit primitives, with the positional
`<name>` acting as a fixed filter. Legacy entries (no agent_name)
never surface here — that's enforced by the same `_filter_entries`
agent check that `clawctl audit show --agent` uses.

Writes go through the top-level `clawctl audit log --agent <name>`;
this surface is intentionally read-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


@pytest.fixture
def audit_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_root = tmp_path / "clawrium"
    monkeypatch.setenv("CLAWRIUM_CONFIG_HOME", str(config_root))
    monkeypatch.delenv("CLAWCTL_AUDIT_SESSION_ID", raising=False)
    # Mark `wolf-i` as a registered agent in hosts.json so the
    # "permissive + soft notice" path (issue #780 iter 6 W1) only
    # fires when the test deliberately uses an unregistered name.
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "hosts.json").write_text(
        json.dumps([
            {"hostname": "test-host", "agents": {"wolf-i": {"type": "openclaw"}}},
        ])
    )
    return config_root / "changelog"


@pytest.fixture
def no_registered_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Like ``audit_home`` but without a hosts.json — every name reads
    as unregistered, so the soft-notice path is unavoidable."""
    config_root = tmp_path / "clawrium"
    monkeypatch.setenv("CLAWRIUM_CONFIG_HOME", str(config_root))
    monkeypatch.delenv("CLAWCTL_AUDIT_SESSION_ID", raising=False)
    return config_root / "changelog"


def _seed(audit_home: Path, *args: Iterable[str]) -> None:
    for cmd in args:
        result = runner.invoke(app, list(cmd))
        assert result.exit_code == 0, result.output


def test_agent_audit_filters_to_positional_only(audit_home: Path) -> None:
    """Other agents and legacy entries must not appear."""
    _seed(
        audit_home,
        ["audit", "log", "legacy op", "--result", "success"],
        ["audit", "log", "wolf op", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "kevin op", "--result", "success", "--agent", "kevin"],
    )
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--json"])
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    actions = [json.loads(ln)["action"] for ln in lines]
    assert actions == ["wolf op"]


def test_agent_audit_renders_formatted_output_with_agent_tag(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "scoped op", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["agent", "audit", "wolf-i"])
    assert result.exit_code == 0
    assert "(wolf-i)" in result.output
    assert "scoped op" in result.output


def test_agent_audit_no_matches_for_registered_agent_is_silent(audit_home: Path) -> None:
    """A registered agent (in hosts.json) with no audit history yields
    a silent empty result — the soft-notice path does NOT fire because
    the empty trail is a legitimate state, not a typo signal."""
    _seed(
        audit_home,
        ["audit", "log", "kevin op", "--result", "success", "--agent", "kevin"],
    )
    result = runner.invoke(app, ["agent", "audit", "wolf-i"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_agent_audit_no_matches_for_unregistered_agent_emits_notice(
    audit_home: Path,
) -> None:
    """Iter-6 W1: when an empty result happens AND the name is not in
    hosts.json, emit a stderr note so typos / deleted agents are
    visible. Exit 0 — empty trails remain valid."""
    result = runner.invoke(app, ["agent", "audit", "wol-fi"])
    assert result.exit_code == 0
    # The notice must surface (CliRunner mixes stderr into output).
    assert "Note:" in result.output
    assert "'wol-fi' is not a registered agent" in result.output


def test_agent_audit_notice_does_not_fire_when_rows_match(audit_home: Path) -> None:
    """If the trail has rows for the name, the notice is suppressed
    even if the name happens to be unregistered — the rows themselves
    are the signal that the name was meaningful at some point."""
    _seed(
        audit_home,
        ["audit", "log", "scoped op", "--result", "success", "--agent", "deleted-agent"],
    )
    result = runner.invoke(app, ["agent", "audit", "deleted-agent"])
    assert result.exit_code == 0
    assert "scoped op" in result.output
    # The soft notice would be a false positive here — the rows prove
    # the name has history.
    assert "is not a registered agent" not in result.output


def test_agent_audit_notice_fires_when_hosts_json_missing(
    no_registered_agents: Path,
) -> None:
    """No hosts.json + empty trail: every name reads as unregistered.
    Notice must surface for every empty result."""
    result = runner.invoke(app, ["agent", "audit", "any-name"])
    assert result.exit_code == 0
    assert "Note:" in result.output


def test_agent_audit_composes_with_filters(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "op1", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "op2", "--result", "failure", "--agent", "wolf-i",
         "--notes", "broken"],
        ["audit", "log", "op3", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(
        app,
        ["agent", "audit", "wolf-i", "--result", "failure", "--json"],
    )
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    actions = [json.loads(ln)["action"] for ln in lines]
    assert actions == ["op2"]


def test_agent_audit_last_n(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "op1", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "op2", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "op3", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "op4", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--last", "2", "--json"])
    assert result.exit_code == 0
    actions = [
        json.loads(ln)["action"] for ln in result.output.splitlines() if ln.strip()
    ]
    assert actions == ["op3", "op4"]


def test_agent_audit_rejects_invalid_actor(audit_home: Path) -> None:
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--actor", "bot"])
    assert result.exit_code == 2
    assert "--actor must be one of" in result.output


def test_agent_audit_rejects_invalid_result(audit_home: Path) -> None:
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--result", "bogus"])
    assert result.exit_code == 2
    assert "--result must be one of" in result.output


def test_agent_audit_does_not_accept_agent_flag(audit_home: Path) -> None:
    """W3: the facade has no --agent escape hatch — the positional IS
    the scope. A future refactor accidentally re-exposing the flag
    would slip past `test_agent_audit_filters_to_positional_only`."""
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--agent", "kevin"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_agent_audit_does_not_accept_all_flag(audit_home: Path) -> None:
    """W3: no --all on the facade either. Operators wanting the global
    view should use `clawctl audit show --all`."""
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--all"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_agent_audit_invalid_grep_regex_exits_with_emit_error(audit_home: Path) -> None:
    """Iter-5 W3 (test-coverage): the facade and the top-level command
    share filter_entries, but a regression in the facade (e.g.
    accidentally swallowing typer.Exit) would not be caught by the
    top-level test. Lock in the same contract on the per-agent surface."""
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--grep", "["])
    assert result.exit_code == 2
    assert "invalid --grep regex" in result.output
    assert "Error:" in result.output
    assert "Hint:" in result.output
