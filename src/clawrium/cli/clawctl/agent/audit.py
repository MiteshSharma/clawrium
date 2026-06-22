"""`clawctl agent audit <name>` — agent-scoped audit trail (issue #780).

A single command that shows the audit trail filtered to one agent.
The positional `<name>` IS the scope — no `--agent` flag, no `--all`
escape hatch — and legacy entries (no agent_name) never surface
here by design.

This is a read-only facade over the public audit primitives in
`src/clawrium/cli/clawctl/audit.py`. For writing, tailing across
days, or summary stats, use `clawctl audit log --agent <name>`,
`clawctl audit tail --agent <name>`, or `clawctl audit stats
--agent <name>` — same data, same filter semantics.

**Permissive name handling** (deliberate departure from the rest of
`clawctl agent <verb> <name>`): the audit trail outlives the agent.
Inspecting the history of a deleted agent is a first-class use case,
so this command does NOT call `safe_resolve_agent`. To still catch
typos, when the result set is empty AND `<name>` is not currently
registered in ``hosts.json``, we emit a one-line stderr notice. The
exit code stays 0 — silent empty results remain valid for genuinely
empty trails of registered agents.
"""

from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from clawrium.cli.clawctl.audit import (
    VALID_ACTORS,
    VALID_RESULTS,
    filter_entries,
    format_entry,
    iter_entries,
    validate_date,
)
from clawrium.cli.output.errors import emit_error
from clawrium.core.hosts import HostsFileCorruptedError, get_agent_by_name

__all__ = ["audit"]


def audit(
    name: str = typer.Argument(..., help="Agent name to scope the read to."),
    date: Optional[str] = typer.Option(None, "--date", help="Restrict to a single UTC day (YYYYMMDD)."),
    actor: Optional[str] = typer.Option(None, "--actor", help="Filter by actor (user|agent)."),
    result: Optional[str] = typer.Option(None, "--result", help="Filter by result (success|failure|skipped)."),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Restrict to one session."),
    grep: Optional[str] = typer.Option(None, "--grep", help="Regex matched against action + notes."),
    last: Optional[int] = typer.Option(None, "--last", help="Only the last N matching entries."),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSONL instead of formatted lines."),
) -> None:
    """Show audit entries for <name>."""
    if actor is not None and actor not in VALID_ACTORS:
        emit_error(
            f"--actor must be one of {VALID_ACTORS}",
            hint="Valid values: user, agent.",
            exit_code=2,
        )
    if result is not None and result not in VALID_RESULTS:
        emit_error(
            f"--result must be one of {VALID_RESULTS}",
            hint="Valid values: success, failure, skipped.",
            exit_code=2,
        )
    validate_date(date)

    entries = filter_entries(
        iter_entries(date),
        actor=actor,
        result=result,
        session_id=session_id,
        agent=name,
        grep=grep,
        last=last,
    )
    if as_json:
        # ensure_ascii=True so raw non-ASCII codepoints (including
        # bidi overrides smuggled into any field) escape to \uXXXX —
        # safe to pipe to a terminal without a downstream sanitize().
        emitted = 0
        for e in entries:
            typer.echo(json.dumps(e, ensure_ascii=True, separators=(",", ":")))
            emitted += 1
    else:
        emitted = 0
        for e in entries:
            typer.echo(format_entry(e))
            emitted += 1

    if emitted == 0 and not _agent_is_registered(name):
        # Empty result + unregistered name → likely typo (or the
        # agent was deleted long ago). Soft notice on stderr; exit
        # code stays 0 because an empty trail is a valid state.
        sys.stderr.write(
            f"Note: {name!r} is not a registered agent "
            f"(typo, or already deleted).\n"
        )


def _agent_is_registered(name: str) -> bool:
    """Return True iff ``name`` resolves to an agent currently present
    in ``hosts.json``. A missing or corrupted hosts file is treated
    as "unknown" rather than raising — the audit trail must remain
    usable even if the local hosts file is broken."""
    try:
        return get_agent_by_name(name) is not None
    except HostsFileCorruptedError:
        return False
