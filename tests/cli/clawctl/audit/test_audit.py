"""Tests for `clawctl audit` — the operator audit-trail subcommand.

These tests exercise the Typer surface end-to-end. The on-disk log
location is redirected via $CLAWRIUM_CONFIG_HOME so each test runs in
isolation in a tmp dir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the audit log root to a tmp dir.

    Also clears any session-id env the host machine might have set, so
    tests that rely on the env-var path start from a clean slate.
    """
    monkeypatch.setenv("CLAWRIUM_CONFIG_HOME", str(tmp_path / "clawrium"))
    monkeypatch.delenv("CLAWCTL_AUDIT_SESSION_ID", raising=False)
    return tmp_path / "clawrium" / "changelog"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _single_log_file(audit_home: Path) -> Path:
    files = sorted(audit_home.glob("*.jsonl"))
    assert len(files) == 1, f"expected 1 log file, found {[f.name for f in files]}"
    return files[0]


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

def test_log_writes_schema_v1_entry(audit_home: Path) -> None:
    result = runner.invoke(
        app,
        ["audit", "log", "clawctl agent start a1", "--result", "success", "--notes", "ok"],
    )
    assert result.exit_code == 0, result.output
    entries = _read_jsonl(_single_log_file(audit_home))
    assert len(entries) == 1
    e = entries[0]
    assert e["type"] == "clawctl_command"
    assert e["actor"] == "agent"
    assert e["action"] == "clawctl agent start a1"
    assert e["result"] == "success"
    assert e["notes"] == "ok"
    # uuid is a uuid4 string
    assert isinstance(e["uuid"], str) and len(e["uuid"]) == 36
    # ms-precision timestamp
    assert e["timestamp"].endswith("Z") and "." in e["timestamp"]
    # version block
    assert e["version"]["audit"] == "1"
    assert "clawctl" in e["version"]
    # cwd captured
    assert isinstance(e["cwd"], str) and e["cwd"]
    # session/parent/agent default to null
    assert e["session_id"] is None
    assert e["parent_uuid"] is None
    assert e["agent_name"] is None


def test_log_with_agent_sets_agent_name(audit_home: Path) -> None:
    """`--agent <name>` populates the new schema field on the row."""
    result = runner.invoke(
        app,
        ["audit", "log", "clawctl agent sync wolf-i", "--result", "success",
         "--agent", "wolf-i"],
    )
    assert result.exit_code == 0, result.output
    e = _read_jsonl(_single_log_file(audit_home))[0]
    assert e["agent_name"] == "wolf-i"


def test_log_actor_user_is_recorded(audit_home: Path) -> None:
    result = runner.invoke(
        app,
        ["audit", "log", "manual clawctl host create 1.2.3.4", "--result", "success", "--actor", "user"],
    )
    assert result.exit_code == 0, result.output
    e = _read_jsonl(_single_log_file(audit_home))[0]
    assert e["actor"] == "user"


def test_log_rejects_invalid_result(audit_home: Path) -> None:
    result = runner.invoke(app, ["audit", "log", "x", "--result", "bogus"])
    assert result.exit_code != 0
    assert "--result must be one of" in result.output


def test_log_rejects_invalid_actor(audit_home: Path) -> None:
    result = runner.invoke(
        app,
        ["audit", "log", "x", "--result", "success", "--actor", "bot"],
    )
    assert result.exit_code != 0
    assert "--actor must be one of" in result.output


def test_log_print_uuid_emits_only_uuid(audit_home: Path) -> None:
    result = runner.invoke(
        app,
        ["audit", "log", "x", "--result", "success", "--print-uuid"],
    )
    assert result.exit_code == 0, result.output
    # Output is exactly one uuid line, no "logged ->" prefix.
    line = result.output.strip()
    assert len(line) == 36, repr(line)
    entry = _read_jsonl(_single_log_file(audit_home))[0]
    assert entry["uuid"] == line


def test_log_parent_uuid_is_recorded(audit_home: Path) -> None:
    parent_run = runner.invoke(
        app, ["audit", "log", "configure", "--result", "success", "--print-uuid"]
    )
    parent_uuid = parent_run.output.strip()

    child_run = runner.invoke(
        app,
        ["audit", "log", "start", "--result", "success", "--parent-uuid", parent_uuid],
    )
    assert child_run.exit_code == 0, child_run.output

    entries = _read_jsonl(_single_log_file(audit_home))
    assert len(entries) == 2
    assert entries[0]["uuid"] == parent_uuid
    assert entries[1]["parent_uuid"] == parent_uuid


def test_log_session_id_from_env(audit_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAWCTL_AUDIT_SESSION_ID", "11111111-2222-3333-4444-555555555555")
    result = runner.invoke(app, ["audit", "log", "x", "--result", "success"])
    assert result.exit_code == 0, result.output
    e = _read_jsonl(_single_log_file(audit_home))[0]
    assert e["session_id"] == "11111111-2222-3333-4444-555555555555"


def test_log_explicit_session_id_overrides_env(audit_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAWCTL_AUDIT_SESSION_ID", "from-env")
    result = runner.invoke(
        app,
        ["audit", "log", "x", "--result", "success", "--session-id", "explicit"],
    )
    assert result.exit_code == 0
    e = _read_jsonl(_single_log_file(audit_home))[0]
    assert e["session_id"] == "explicit"


# ---------------------------------------------------------------------------
# show / tail / stats
# ---------------------------------------------------------------------------

def _seed(audit_home: Path, *args: Iterable[str]) -> None:
    for cmd in args:
        result = runner.invoke(app, list(cmd))
        assert result.exit_code == 0, result.output


def test_show_filter_by_result(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "clawctl agent start a1", "--result", "success"],
        ["audit", "log", "clawctl agent stop a2", "--result", "failure", "--notes", "broken"],
        ["audit", "log", "clawctl agent sync a3", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "show", "--all", "--result", "failure"])
    assert result.exit_code == 0
    assert "clawctl agent stop a2" in result.output
    assert "clawctl agent start a1" not in result.output
    assert "clawctl agent sync a3" not in result.output


def test_show_filter_by_session_id(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "alpha", "--result", "success", "--session-id", "S1"],
        ["audit", "log", "beta", "--result", "success", "--session-id", "S2"],
        ["audit", "log", "gamma", "--result", "success", "--session-id", "S1"],
    )
    result = runner.invoke(app, ["audit", "show", "--all", "--session-id", "S1", "--json"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    actions = [json.loads(ln)["action"] for ln in lines]
    assert sorted(actions) == ["alpha", "gamma"]


def test_show_grep_matches_action_and_notes(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "foo", "--result", "success", "--notes", "deploy myassistant"],
        ["audit", "log", "bar", "--result", "success"],
        ["audit", "log", "myassistant boot", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "show", "--all", "--grep", "myassistant", "--json"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 2
    actions = sorted(json.loads(ln)["action"] for ln in lines)
    assert actions == ["foo", "myassistant boot"]


def test_show_last_n_returns_tail_after_filters(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "a", "--result", "success"],
        ["audit", "log", "b", "--result", "success"],
        ["audit", "log", "c", "--result", "success"],
        ["audit", "log", "d", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "show", "--all", "--last", "2", "--json"])
    assert result.exit_code == 0
    actions = [json.loads(ln)["action"] for ln in result.output.splitlines() if ln.strip()]
    assert actions == ["c", "d"]


def test_tail_default_returns_recent(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "first", "--result", "success"],
        ["audit", "log", "second", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "tail", "--all"])
    assert result.exit_code == 0
    out = result.output
    assert "first" in out and "second" in out
    # second must come after first
    assert out.index("first") < out.index("second")


def test_stats_summarises_by_actor_result_verb(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "clawctl agent start a1", "--result", "success"],
        ["audit", "log", "clawctl agent stop a1", "--result", "failure", "--notes", "x"],
        ["audit", "log", "clawctl host create 1.2.3.4", "--actor", "user", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "stats", "--all", "--top", "5"])
    assert result.exit_code == 0
    out = result.output
    assert "Total entries:     3" in out
    assert "'agent': 2" in out and "'user': 1" in out
    assert "'success': 2" in out and "'failure': 1" in out
    assert "clawctl agent" in out
    assert "clawctl host" in out


def test_stats_on_empty_trail_returns_zero(audit_home: Path) -> None:
    result = runner.invoke(app, ["audit", "stats", "--all"])
    assert result.exit_code == 0
    assert "Total entries:     0" in result.output


def test_show_without_scope_errors(audit_home: Path) -> None:
    """Issue #780: show requires --agent or --all explicitly."""
    result = runner.invoke(app, ["audit", "show"])
    assert result.exit_code == 2
    assert "--agent" in result.output and "--all" in result.output


def test_show_agent_and_all_are_mutually_exclusive(audit_home: Path) -> None:
    result = runner.invoke(app, ["audit", "show", "--agent", "wolf-i", "--all"])
    assert result.exit_code == 2
    assert "audit show: --agent and --all are mutually exclusive" in result.output


def test_tail_agent_and_all_are_mutually_exclusive(audit_home: Path) -> None:
    """W1: mutex contract must hold for tail too."""
    result = runner.invoke(app, ["audit", "tail", "--agent", "wolf-i", "--all"])
    assert result.exit_code == 2
    assert "audit tail: --agent and --all are mutually exclusive" in result.output
    # Iter-2 W5: mutex errors must carry a recovery Hint, same as the
    # scope-required errors.
    assert "Hint:" in result.output
    assert "Pass exactly one of --agent <name> or --all." in result.output


def test_stats_agent_and_all_are_mutually_exclusive(audit_home: Path) -> None:
    """W1: mutex contract must hold for stats too."""
    result = runner.invoke(app, ["audit", "stats", "--agent", "wolf-i", "--all"])
    assert result.exit_code == 2
    assert "audit stats: --agent and --all are mutually exclusive" in result.output
    assert "Hint:" in result.output
    assert "Pass exactly one of --agent <name> or --all." in result.output


def test_show_mutex_error_carries_hint(audit_home: Path) -> None:
    """Iter-2 W5: show mutex must also surface the Hint line."""
    result = runner.invoke(app, ["audit", "show", "--agent", "wolf-i", "--all"])
    assert result.exit_code == 2
    assert "Hint:" in result.output
    assert "Pass exactly one of --agent <name> or --all." in result.output


def test_tail_agent_filters_to_named_agent(audit_home: Path) -> None:
    """W2: `audit tail --agent <name>` actually filters by agent."""
    _seed(
        audit_home,
        ["audit", "log", "legacy op", "--result", "success"],
        ["audit", "log", "wolf-a", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "kevin-a", "--result", "success", "--agent", "kevin"],
        ["audit", "log", "wolf-b", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["audit", "tail", "--agent", "wolf-i"])
    assert result.exit_code == 0
    out = result.output
    assert "wolf-a" in out and "wolf-b" in out
    assert "kevin-a" not in out
    assert "legacy op" not in out


def test_scope_required_error_mentions_agent_audit(audit_home: Path) -> None:
    """W5: scope-required error must surface 'clawctl agent audit <name>'
    as a discoverable alternative."""
    result = runner.invoke(app, ["audit", "show"])
    assert result.exit_code == 2
    assert "clawctl agent audit" in result.output


def test_scope_required_error_uses_emit_error_format(audit_home: Path) -> None:
    """W4: errors must route through emit_error (Error: <msg> + Hint: ...)."""
    result = runner.invoke(app, ["audit", "show"])
    assert result.exit_code == 2
    assert "Error:" in result.output
    assert "Hint:" in result.output


def test_format_entry_strips_bidi_from_agent_name(audit_home: Path) -> None:
    """B2: agent_name must be sanitized before terminal emission so a
    smuggled bidi codepoint cannot reverse-render the row."""
    audit_home.mkdir(parents=True, exist_ok=True)
    smuggled = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000aaa",
        "parent_uuid": None,
        "session_id": None,
        # U+202E RIGHT-TO-LEFT OVERRIDE smuggled into the agent name.
        "agent_name": "wolf‮i",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "agent",
        "action": "clawctl agent sync wolf-i",
        "result": "success",
        "notes": "",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(smuggled, ensure_ascii=False) + "\n")

    result = runner.invoke(app, ["audit", "show", "--all"])
    assert result.exit_code == 0
    # The raw bidi codepoint must NOT appear in formatted output.
    assert "‮" not in result.output


def test_format_entry_strips_bidi_via_agent_audit_facade(audit_home: Path) -> None:
    """B2: the `clawctl agent audit <name>` facade must also sanitize."""
    audit_home.mkdir(parents=True, exist_ok=True)
    smuggled = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000bbb",
        "parent_uuid": None,
        "session_id": None,
        "agent_name": "wolf-i",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "agent",
        # Bidi smuggled into the action field instead.
        "action": "clawctl agent sync wolf‮i",
        "result": "success",
        "notes": "trust‮me",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(smuggled, ensure_ascii=False) + "\n")

    result = runner.invoke(app, ["agent", "audit", "wolf-i"])
    assert result.exit_code == 0
    assert "‮" not in result.output


def test_show_agent_filters_out_legacy_entries(audit_home: Path) -> None:
    """An entry with no agent_name MUST NOT match --agent <name>."""
    _seed(
        audit_home,
        ["audit", "log", "legacy op", "--result", "success"],
        ["audit", "log", "scoped op", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["audit", "show", "--agent", "wolf-i", "--json"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    actions = [json.loads(ln)["action"] for ln in lines]
    assert actions == ["scoped op"]


def test_show_all_surfaces_legacy_entries(audit_home: Path) -> None:
    """--all is the only way to see entries that pre-date the agent_name field."""
    _seed(
        audit_home,
        ["audit", "log", "legacy op", "--result", "success"],
        ["audit", "log", "scoped op", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["audit", "show", "--all", "--json"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    actions = sorted(json.loads(ln)["action"] for ln in lines)
    assert actions == ["legacy op", "scoped op"]


def test_format_includes_agent_column_when_present(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "scoped op", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["audit", "show", "--all"])
    assert result.exit_code == 0
    assert "(wolf-i)" in result.output


def test_format_omits_agent_column_when_absent(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "legacy op", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "show", "--all"])
    assert result.exit_code == 0
    # No parenthesised agent block should appear in the line — tighter
    # than the previous "before success" check.
    assert "(wolf-i)" not in result.output
    assert "(" not in result.output


def test_format_truncates_long_agent_name(audit_home: Path) -> None:
    """Iter-2 W4 + iter-3 W3: agent names exceeding AGENT_COL_WIDTH-2 must
    be ellipsis-truncated AND the slot must stay exactly AGENT_COL_WIDTH
    chars wide so column alignment survives."""
    from clawrium.cli.clawctl.audit import AGENT_COL_WIDTH

    long_name = "a" * (AGENT_COL_WIDTH * 2)  # well past the slot
    _seed(
        audit_home,
        ["audit", "log", "op-long", "--result", "success", "--agent", long_name],
        # Seed a short-name row to establish the canonical column offset.
        ["audit", "log", "op-short", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["audit", "show", "--all"])
    assert result.exit_code == 0
    # The ellipsis marker is present and the full name is not.
    assert "…" in result.output
    assert long_name not in result.output
    # Iter-3 W3: the result column lands at the same offset for both
    # rows — locks in the .ljust(AGENT_COL_WIDTH) padding contract.
    long_line = next(ln for ln in result.output.splitlines() if "op-long" in ln)
    short_line = next(ln for ln in result.output.splitlines() if "op-short" in ln)
    assert long_line.index("success") == short_line.index("success")


def test_format_mixed_listing_aligns_result_column(audit_home: Path) -> None:
    """Iter-2 W4: scoped and unscoped rows must place 'success' at the
    same column offset so listings stay vertically aligned."""
    _seed(
        audit_home,
        ["audit", "log", "legacy op", "--result", "success"],
        ["audit", "log", "scoped op", "--result", "success", "--agent", "wolf-i"],
    )
    result = runner.invoke(app, ["audit", "show", "--all"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if "success" in ln]
    assert len(lines) == 2
    # Both lines should have 'success' at the same index — the
    # AGENT_COL_WIDTH padding contract is what makes this true.
    offsets = {ln.index("success") for ln in lines}
    assert len(offsets) == 1, f"misaligned result column: {offsets}"


def test_stats_by_agent_breakdown(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "op1", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "op2", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "op3", "--result", "success", "--agent", "kevin"],
        ["audit", "log", "op4", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "stats", "--all"])
    assert result.exit_code == 0
    out = result.output
    assert "By agent:" in out
    assert "'wolf-i': 2" in out
    assert "'kevin': 1" in out
    assert "'(unscoped)': 1" in out


def test_stats_agent_scopes_counts(audit_home: Path) -> None:
    _seed(
        audit_home,
        ["audit", "log", "op1", "--result", "success", "--agent", "wolf-i"],
        ["audit", "log", "op2", "--result", "failure", "--agent", "wolf-i"],
        ["audit", "log", "op3", "--result", "success", "--agent", "kevin"],
        # Iter-2 W9: include an unscoped entry to confirm it doesn't leak.
        ["audit", "log", "legacy op", "--result", "success"],
    )
    result = runner.invoke(app, ["audit", "stats", "--agent", "wolf-i"])
    assert result.exit_code == 0
    out = result.output
    assert "Total entries:     2" in out
    assert "'success': 1" in out and "'failure': 1" in out
    assert "'kevin'" not in out
    # Iter-2 W9: legacy/unscoped rows must not contaminate scoped stats.
    assert "(unscoped)" not in out


@pytest.mark.parametrize(
    "field,value,marker",
    [
        # Iter-3 W2: every Counter key and Top-N verb must strip bidi
        # before terminal emission.
        ("actor", "agent‮x", "‮"),
        ("result", "success‮x", "‮"),
        ("action", "clawctl agent sync‮x wolf", "‮"),
    ],
)
def test_stats_sanitizes_all_counter_paths(
    audit_home: Path, field: str, value: str, marker: str,
) -> None:
    """Iter-3 W1+W2: every Counter key (actor/result/verb/agent) and
    the Top-N verb emission must strip smuggled bidi codepoints."""
    audit_home.mkdir(parents=True, exist_ok=True)
    row = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000111",
        "parent_uuid": None,
        "session_id": None,
        "agent_name": None,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "agent",
        "action": "op",
        "result": "success",
        "notes": "",
    }
    row[field] = value
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(row, ensure_ascii=False) + "\n")

    result = runner.invoke(app, ["audit", "stats", "--all"])
    assert result.exit_code == 0
    assert marker not in result.output


def test_stats_by_agent_sanitizes_smuggled_bidi(audit_home: Path) -> None:
    """Iter-2 B1: agent_name carries to the stats `By agent:` line via
    Counter; bidi codepoints must be stripped before terminal emission."""
    audit_home.mkdir(parents=True, exist_ok=True)
    smuggled = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000ccc",
        "parent_uuid": None,
        "session_id": None,
        # U+202E smuggled into agent_name (\u escape for source hygiene).
        "agent_name": "wolf‮i",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "agent",
        "action": "op",
        "result": "success",
        "notes": "",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(smuggled, ensure_ascii=False) + "\n")

    result = runner.invoke(app, ["audit", "stats", "--all"])
    assert result.exit_code == 0
    assert "By agent:" in result.output
    # The raw bidi codepoint must NOT appear anywhere in the stats output.
    assert "‮" not in result.output


def test_json_path_escapes_smuggled_bidi(audit_home: Path) -> None:
    """Iter-2 W3: --json paths must use ensure_ascii=True so bidi codepoints
    escape to \\uXXXX rather than passing through to the terminal."""
    audit_home.mkdir(parents=True, exist_ok=True)
    smuggled = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000ddd",
        "parent_uuid": None,
        "session_id": None,
        "agent_name": "wolf-i",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "agent",
        "action": "op‮-smuggled",
        "result": "success",
        "notes": "",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(smuggled, ensure_ascii=False) + "\n")

    result = runner.invoke(app, ["audit", "show", "--all", "--json"])
    assert result.exit_code == 0
    # Raw bidi codepoint stripped; \uXXXX escape present instead.
    assert "‮" not in result.output
    assert "\\u202e" in result.output
    # JSON still parses round-trip back to the original codepoint.
    parsed = json.loads(result.output.strip().splitlines()[0])
    assert parsed["action"] == "op‮-smuggled"


def test_agent_audit_json_path_escapes_smuggled_bidi(audit_home: Path) -> None:
    """Iter-2 W3: same contract for the per-agent facade's --json output."""
    audit_home.mkdir(parents=True, exist_ok=True)
    smuggled = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000eee",
        "parent_uuid": None,
        "session_id": None,
        "agent_name": "wolf-i",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "agent",
        "action": "op‮-smuggled",
        "result": "success",
        "notes": "",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(smuggled, ensure_ascii=False) + "\n")

    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--json"])
    assert result.exit_code == 0
    assert "‮" not in result.output
    assert "\\u202e" in result.output


@pytest.mark.parametrize("verb", ["show", "tail", "stats"])
def test_scope_required_error_uses_emit_error_across_all_verbs(
    audit_home: Path, verb: str,
) -> None:
    """Iter-3 W4: every read verb routes scope-required errors through
    emit_error (Error: + Hint:). A regression bypassing emit_error for
    tail or stats (reverting to raw typer.echo) is caught here."""
    result = runner.invoke(app, ["audit", verb])
    assert result.exit_code == 2
    assert "Error:" in result.output
    assert "Hint:" in result.output
    assert "--agent" in result.output
    assert "--all" in result.output
    assert "clawctl agent audit" in result.output


def test_tail_requires_scope(audit_home: Path) -> None:
    result = runner.invoke(app, ["audit", "tail"])
    assert result.exit_code == 2
    assert "--agent" in result.output and "--all" in result.output


def test_stats_requires_scope(audit_home: Path) -> None:
    result = runner.invoke(app, ["audit", "stats"])
    assert result.exit_code == 2
    assert "--agent" in result.output and "--all" in result.output


def test_show_rejects_invalid_actor(audit_home: Path) -> None:
    """Iter-3 W5: show's --actor validation routes through emit_error."""
    result = runner.invoke(app, ["audit", "show", "--all", "--actor", "bot"])
    assert result.exit_code == 2
    assert "--actor must be one of" in result.output
    assert "Error:" in result.output


def test_show_rejects_invalid_result(audit_home: Path) -> None:
    """Iter-3 W5: show's --result validation routes through emit_error."""
    result = runner.invoke(app, ["audit", "show", "--all", "--result", "bogus"])
    assert result.exit_code == 2
    assert "--result must be one of" in result.output
    assert "Error:" in result.output


def test_show_invalid_grep_regex_exits_with_emit_error(audit_home: Path) -> None:
    """Iter-4: a malformed --grep regex must surface a clean error,
    not a Python traceback. re.error wrapped in emit_error."""
    result = runner.invoke(app, ["audit", "show", "--all", "--grep", "["])
    assert result.exit_code == 2
    assert "invalid --grep regex" in result.output
    assert "Error:" in result.output
    assert "Hint:" in result.output


def test_show_invalid_date_format_exits_with_emit_error(audit_home: Path) -> None:
    """Iter-4: --date must match ^\\d{8}$ to prevent typos producing
    silently-empty results and to keep the interpolated log path bounded."""
    result = runner.invoke(app, ["audit", "show", "--all", "--date", "2026-06-21"])
    assert result.exit_code == 2
    assert "--date must be 8 digits" in result.output
    assert "Error:" in result.output


def test_agent_audit_invalid_date_format_exits_with_emit_error(audit_home: Path) -> None:
    """Iter-4: same --date validation on the agent-scoped facade.
    Iter-5: also assert Error:/Hint: format for parity with the
    top-level test."""
    result = runner.invoke(app, ["agent", "audit", "wolf-i", "--date", "bad"])
    assert result.exit_code == 2
    assert "--date must be 8 digits" in result.output
    assert "Error:" in result.output
    assert "Hint:" in result.output


def test_show_valid_date_actually_filters_by_day(audit_home: Path) -> None:
    """Iter-4 introduced --date format validation; iter-5 W1 hardens
    this test to also prove the date actually filters the result.
    Seed entries across two days and assert --date selects the right
    one. (The previous empty-trail variant proved nothing about
    filter behaviour — only that validation accepted the format.)"""
    audit_home.mkdir(parents=True, exist_ok=True)

    def _row(uid_suffix: str, action: str) -> dict:
        return {
            "type": "clawctl_command",
            "uuid": f"00000000-0000-4000-8000-00000000{uid_suffix}",
            "parent_uuid": None,
            "session_id": None,
            "agent_name": None,
            "timestamp": "2026-01-01T00:00:00.000Z",
            "cwd": "/tmp",
            "version": {"audit": "1", "clawctl": "0.0.0"},
            "actor": "user",
            "action": action,
            "result": "success",
            "notes": "",
        }

    (audit_home / "20260101.jsonl").write_text(
        json.dumps(_row("0a01", "day-1 op")) + "\n"
    )
    (audit_home / "20260202.jsonl").write_text(
        json.dumps(_row("0a02", "day-2 op")) + "\n"
    )

    day1 = runner.invoke(
        app, ["audit", "show", "--all", "--date", "20260101", "--json"]
    )
    assert day1.exit_code == 0
    actions = [
        json.loads(ln)["action"] for ln in day1.output.splitlines() if ln.strip()
    ]
    assert actions == ["day-1 op"]


def test_show_valid_date_on_empty_day_returns_nothing(audit_home: Path) -> None:
    """Iter-4: well-formed --date with no log file for that day is a
    silent empty result, not an error."""
    result = runner.invoke(app, ["audit", "show", "--all", "--date", "19990101"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_format_tolerates_non_string_field_values(audit_home: Path) -> None:
    """Iter-3 B2: a row with timestamp/actor/result/action as null or a
    non-string scalar must NOT crash format_entry — degrade to '?'
    placeholders and keep the rest of the trail readable."""
    audit_home.mkdir(parents=True, exist_ok=True)
    malformed = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000222",
        "parent_uuid": None,
        "session_id": None,
        "agent_name": None,
        # All four format-spec fields hostile to :24s/:5s/:7s/str interp.
        "timestamp": None,
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": 5,
        "action": None,
        "result": ["nested"],
        "notes": 42,
    }
    well_formed = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000333",
        "parent_uuid": None,
        "session_id": None,
        "agent_name": "wolf-i",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "agent",
        "action": "survivor",
        "result": "success",
        "notes": "",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(
        json.dumps(malformed) + "\n" + json.dumps(well_formed) + "\n"
    )

    # show must NOT crash on the malformed row — exit 0 and emit the
    # well-formed row intact.
    result = runner.invoke(app, ["audit", "show", "--all"])
    assert result.exit_code == 0, result.output
    assert "survivor" in result.output

    # stats must not crash either (B2 also affects the date-bucket
    # `ts[:10]` slice on a non-string timestamp).
    stats_result = runner.invoke(app, ["audit", "stats", "--all"])
    assert stats_result.exit_code == 0


def test_iter_read_tolerates_missing_agent_field(audit_home: Path) -> None:
    """Hand-write a pre-#780 row (no agent_name key) and confirm reads work."""
    audit_home.mkdir(parents=True, exist_ok=True)
    legacy = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000001",
        "parent_uuid": None,
        "session_id": None,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "user",
        "action": "legacy hand-written",
        "result": "success",
        "notes": "",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(legacy) + "\n")

    result = runner.invoke(app, ["audit", "show", "--all", "--json"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["action"] == "legacy hand-written"
    # Round-trip stayed faithful: missing key passed through, not synthesised.
    assert "agent_name" not in parsed


def test_iter_read_tolerates_explicit_null_agent_field(audit_home: Path) -> None:
    """Iter-2 W7: a row with ``"agent_name": null`` (vs the key being
    absent) must be treated as unscoped — same filter behavior, same
    stats bucket. Distinct case from `test_iter_read_tolerates_missing_agent_field`."""
    audit_home.mkdir(parents=True, exist_ok=True)
    null_field = {
        "type": "clawctl_command",
        "uuid": "00000000-0000-4000-8000-000000000fff",
        "parent_uuid": None,
        "session_id": None,
        "agent_name": None,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "cwd": "/tmp",
        "version": {"audit": "1", "clawctl": "0.0.0"},
        "actor": "user",
        "action": "explicit-null row",
        "result": "success",
        "notes": "",
    }
    log_file = audit_home / "20260101.jsonl"
    log_file.write_text(json.dumps(null_field) + "\n")

    # Filter behaviour: --agent <name> must NOT match an explicit-null row.
    scoped = runner.invoke(app, ["audit", "show", "--agent", "anyone", "--json"])
    assert scoped.exit_code == 0
    assert scoped.output.strip() == ""

    # --all surfaces it.
    all_view = runner.invoke(app, ["audit", "show", "--all", "--json"])
    assert all_view.exit_code == 0
    assert "explicit-null row" in all_view.output

    # Stats: bucketed under the same "(unscoped)" label as missing-key rows.
    stats_view = runner.invoke(app, ["audit", "stats", "--all"])
    assert stats_view.exit_code == 0
    assert "(unscoped)" in stats_view.output


def test_show_all_on_empty_trail_prints_nothing(audit_home: Path) -> None:
    """Iter-2 W8: empty trail under --all is silent success."""
    result = runner.invoke(app, ["audit", "show", "--all"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_show_agent_on_empty_trail_prints_nothing(audit_home: Path) -> None:
    """Iter-2 W8: empty trail under --agent <name> is silent success."""
    result = runner.invoke(app, ["audit", "show", "--agent", "wolf-i"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


# ---------------------------------------------------------------------------
# session / path
# ---------------------------------------------------------------------------

def test_session_new_emits_uuid4(audit_home: Path) -> None:
    result = runner.invoke(app, ["audit", "session", "new"])
    assert result.exit_code == 0
    sid = result.output.strip()
    assert len(sid) == 36
    # Calling twice gives different ids.
    second = runner.invoke(app, ["audit", "session", "new"]).output.strip()
    assert sid != second


def test_path_prints_changelog_dir(audit_home: Path) -> None:
    result = runner.invoke(app, ["audit", "path"])
    assert result.exit_code == 0
    assert result.output.strip().endswith("clawrium/changelog")


# ---------------------------------------------------------------------------
# Read tolerance
# ---------------------------------------------------------------------------

def test_iter_entries_skips_malformed_lines(audit_home: Path) -> None:
    """A corrupt line must not block reading the rest of the trail."""
    # Seed two good entries.
    _seed(
        audit_home,
        ["audit", "log", "good1", "--result", "success"],
        ["audit", "log", "good2", "--result", "success"],
    )
    log_file = _single_log_file(audit_home)
    # Inject a malformed line between the good ones.
    raw = log_file.read_text().splitlines()
    log_file.write_text(raw[0] + "\n" + "{not-json\n" + raw[1] + "\n")

    result = runner.invoke(app, ["audit", "show", "--all", "--json"])
    assert result.exit_code == 0
    actions = [json.loads(ln)["action"] for ln in result.output.splitlines() if ln.strip()]
    assert actions == ["good1", "good2"]
