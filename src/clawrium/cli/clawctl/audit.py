"""`clawctl audit` — operator audit trail for the /clawctl skill.

The audit trail is the operator-side record of every mutating clawctl
operation performed by a human operator or by an AI assistant using the
/clawctl skill. Logs live as one JSONL file per UTC day under
``$XDG_CONFIG_HOME/clawrium/changelog/`` (defaulting to
``~/.config/clawrium/changelog/``). The schema is documented at the top
of ``build_entry`` below.

This module replaces the prior standalone ``scripts/clawctl-audit.py``;
shipping the tool as a clawctl subcommand means anyone with clawctl on
PATH also has ``clawctl audit`` available — there is no separate PATH
plumbing for the /clawctl skill to depend on.
"""

from __future__ import annotations

import json
import os
import re
import uuid as uuidlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

import typer

from clawrium import __version__ as _clawctl_version
from clawrium.cli.output._sanitize import sanitize
from clawrium.cli.output.errors import emit_error

__all__ = [
    "audit_app",
    "audit_session_app",
    # Public API consumed by clawrium.cli.clawctl.agent.audit (the
    # per-agent read facade for issue #780). Promoted from underscore-
    # prefixed privates in #780 so the cross-module boundary is
    # explicit and rename-safe.
    "VALID_ACTORS",
    "VALID_RESULTS",
    "iter_entries",
    "filter_entries",
    "format_entry",
    "action_verb",
    "validate_date",
]


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

VALID_ACTORS = ("user", "agent")
VALID_RESULTS = ("success", "failure", "skipped")
_DEFAULT_TYPE = "clawctl_command"
_SCHEMA_VERSION = "1"
_SESSION_ENV_VAR = "CLAWCTL_AUDIT_SESSION_ID"


# ---------------------------------------------------------------------------
# Storage layout
# ---------------------------------------------------------------------------

def _config_root() -> Path:
    """Return the clawrium config root.

    Resolution order:
      1. ``$CLAWRIUM_CONFIG_HOME`` — test/override hook.
      2. ``$XDG_CONFIG_HOME/clawrium`` — Linux convention.
      3. ``~/.config/clawrium`` — default.
    """
    override = os.environ.get("CLAWRIUM_CONFIG_HOME")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "clawrium"


def _log_dir() -> Path:
    return _config_root() / "changelog"


def _log_path_for(dt: datetime) -> Path:
    return _log_dir() / f"{dt.strftime('%Y%m%d')}.jsonl"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso_ms() -> str:
    """ISO 8601 UTC with millisecond precision, e.g. ``2026-06-17T18:23:00.123Z``."""
    now = _utc_now()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Read / write primitives
# ---------------------------------------------------------------------------

def _build_entry(
    *,
    action: str,
    result: str,
    actor: str,
    notes: str = "",
    session_id: Optional[str] = None,
    parent_uuid: Optional[str] = None,
    agent_name: Optional[str] = None,
    entry_type: str = _DEFAULT_TYPE,
) -> dict:
    """Construct a schema-v1 entry.

    Required fields (every entry):
      type        -- discriminator; "clawctl_command" today
      uuid        -- uuid4, unique per entry
      parent_uuid -- causal parent's uuid (or None)
      session_id  -- workflow grouping id (or None)
      agent_name  -- agent this op touched (or None for unscoped)
      timestamp   -- ISO 8601 UTC with ms precision
      cwd         -- captured os.getcwd() at write time
      version     -- {"audit": "<schema>", "clawctl": "<clawctl>"}
      actor       -- "user" | "agent"
      action      -- short description / literal command
      result      -- "success" | "failure" | "skipped"
      notes       -- free text; "" allowed

    Schema-v1 additive boundary (issue #780): ``agent_name`` was
    introduced after the initial v1 schema. Entries written
    pre-#780 do NOT contain the ``agent_name`` key at all
    (distinct from ``"agent_name": null``). Readers MUST treat
    missing-key and ``None`` as equivalent ("unscoped") and MUST
    NOT branch on key presence alone. The schema version stays at
    "1" because reads are tolerant by design; no migration is
    required.
    """
    return {
        "type": entry_type,
        "uuid": str(uuidlib.uuid4()),
        "parent_uuid": parent_uuid,
        "session_id": session_id,
        "agent_name": agent_name,
        "timestamp": _utc_now_iso_ms(),
        "cwd": os.getcwd(),
        "version": {
            "audit": _SCHEMA_VERSION,
            "clawctl": _clawctl_version,
        },
        "actor": actor,
        "action": action,
        "result": result,
        "notes": notes or "",
    }


def _append_entry(entry: dict) -> Path:
    target = _log_path_for(_utc_now())
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
    with target.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return target


def iter_entries(date: Optional[str] = None) -> Iterator[dict]:
    """Yield entries from one day's log, or from every log on disk.

    Malformed lines are silently skipped so a corrupt write never blocks
    reading the rest of the trail.
    """
    root = _log_dir()
    if not root.exists():
        return
    if date:
        files = [root / f"{date}.jsonl"]
    else:
        files = sorted(root.glob("*.jsonl"))
    for f in files:
        if not f.is_file():
            continue
        with f.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


#: Width of the agent_name column when rendered in formatted output.
#: Chosen to fit common per-instance names (e.g. ``wolf-i``,
#: ``mybox-openclaw``) without truncation while keeping the
#: result/action columns vertically aligned across mixed listings of
#: scoped and legacy (unscoped) rows. Names longer than this are
#: truncated with an ellipsis.
AGENT_COL_WIDTH = 18


def format_entry(e: dict) -> str:
    """Render one entry as a single human-readable line.

    Every interpolated field is operator-controlled (the JSONL row
    is read from disk, where any actor with write access could have
    smuggled bidi codepoints into ``timestamp``, ``actor``,
    ``result``, ``session_id``, ``agent_name``, ``action``, or
    ``notes``). We sanitize the entire rendered line at the output
    boundary rather than per-field — one call, no missed surface
    area, and idempotent on already-safe strings.

    All field reads pass through ``str(... or '?')`` so a JSONL row
    with a non-string typed scalar (``"timestamp": null``,
    ``"actor": 5``) does NOT raise ``TypeError`` against the
    ``:24s`` / ``:5s`` / ``:7s`` format specs. A malformed row
    degrades to ``"?"`` placeholders instead of taking down the
    entire ``show``/``tail`` invocation.
    """
    notes_raw = e.get("notes") or ""
    notes = str(notes_raw)
    tail = f"  -- {notes}" if notes else ""
    sess = e.get("session_id")
    sess_tag = f" {str(sess)[:8]}" if sess else ""
    agent = e.get("agent_name")
    # Fixed-width agent slot so the result/action columns line up
    # across mixed listings (scoped + legacy). When agent_name is
    # absent we emit AGENT_COL_WIDTH spaces; when present we render
    # ``(name)`` padded/truncated to the same width.
    if agent:
        inner = str(agent)
        # Reserve 2 chars for the parens; truncate the body if needed.
        body_max = AGENT_COL_WIDTH - 2
        if len(inner) > body_max:
            inner = inner[: body_max - 1] + "…"
        agent_slot = f"({inner})".ljust(AGENT_COL_WIDTH)
    else:
        agent_slot = " " * AGENT_COL_WIDTH
    ts = str(e.get("timestamp") or "?")
    actor = str(e.get("actor") or "?")
    result = str(e.get("result") or "?")
    action = str(e.get("action") or "?")
    line = (
        f"{ts:24s}  "
        f"[{actor:5s}]  "
        f"{agent_slot}  "
        f"{result:7s}  "
        f"{action}{sess_tag}{tail}"
    )
    return sanitize(line)


def action_verb(action: str) -> str:
    """Coarse grouping for ``stats`` output.

    Almost every action will start with ``clawctl``, so the leading token
    alone is uninformative. When the action begins with ``clawctl`` we use
    the first two tokens (``clawctl agent``, ``clawctl host``) — the
    granularity an operator usually wants in a summary.
    """
    if not action:
        return "?"
    tokens = action.split()
    if tokens and tokens[0] == "clawctl" and len(tokens) >= 2:
        return f"clawctl {tokens[1]}"
    return tokens[0]


def filter_entries(entries: Iterator[dict], *,
                    actor: Optional[str],
                    result: Optional[str],
                    session_id: Optional[str],
                    agent: Optional[str],
                    grep: Optional[str],
                    last: Optional[int]) -> List[dict]:
    out = list(entries)
    if actor:
        out = [e for e in out if e.get("actor") == actor]
    if result:
        out = [e for e in out if e.get("result") == result]
    if session_id:
        out = [e for e in out if e.get("session_id") == session_id]
    if agent:
        out = [e for e in out if e.get("agent_name") == agent]
    if grep:
        try:
            pat = re.compile(grep)
        except re.error as exc:
            emit_error(
                f"invalid --grep regex: {exc}",
                hint="Pass a valid Python regex; escape literal metacharacters.",
                exit_code=2,
            )
            # Defensive: emit_error is annotated NoReturn, but a future
            # refactor that demoted it to a regular return would leave
            # `pat` unbound on the line below. Make the exit explicit
            # so the failure mode at that point is `SystemExit`, not
            # `NameError`.
            raise typer.Exit(code=2)
        def matches(e: dict) -> bool:
            haystack = " ".join([
                str(e.get("action", "")),
                str(e.get("notes", "")),
            ])
            return bool(pat.search(haystack))
        out = [e for e in out if matches(e)]
    if last:
        out = out[-last:]
    return out


#: ``[0-9]`` rather than ``\d`` deliberately — ``\d`` matches any
#: Unicode Nd digit, which is imprecise even though no Nd codepoint
#: would form a path-traversal sequence here.
_DATE_FORMAT_RE = re.compile(r"^[0-9]{8}$")


def validate_date(date: Optional[str]) -> None:
    """Reject ``--date`` values that don't match the YYYYMMDD log naming.

    The value is interpolated into the log file path. Even though the
    audit log directory is operator-local (so path-traversal risk is
    negligible), a format guard catches typos at entry rather than
    producing a silently empty result when the file doesn't exist.
    """
    if date is None:
        return
    if not _DATE_FORMAT_RE.match(date):
        emit_error(
            f"--date must be 8 digits (YYYYMMDD); got {date!r}",
            hint="Example: --date 20260621 for 2026-06-21.",
            exit_code=2,
        )


def _require_scope(agent: Optional[str], all_flag: bool, *, verb: str) -> None:
    """Enforce the issue #780 contract: every read verb is agent-scoped by
    default. The operator must either name an agent (`--agent`) or opt into
    the unscoped global view (`--all`)."""
    if agent and all_flag:
        emit_error(
            f"audit {verb}: --agent and --all are mutually exclusive",
            hint="Pass exactly one of --agent <name> or --all.",
            exit_code=2,
        )
    if not agent and not all_flag:
        emit_error(
            f"audit {verb}: must pass --agent <name> or --all",
            hint=(
                "--all surfaces every entry, including legacy rows that pre-date "
                "the agent_name field. For one agent, use --agent <name> or run "
                "'clawctl agent audit <name>'."
            ),
            exit_code=2,
        )


# ---------------------------------------------------------------------------
# Typer apps
# ---------------------------------------------------------------------------

audit_app = typer.Typer(
    name="audit",
    help="Operator audit trail for the /clawctl skill.",
    no_args_is_help=True,
    rich_markup_mode=None,
    add_completion=False,
)

audit_session_app = typer.Typer(
    name="session",
    help="Manage session ids for grouping a workflow's entries.",
    no_args_is_help=True,
    rich_markup_mode=None,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

@audit_app.command("log", help="Append an entry to today's audit log.")
def log(
    action: str = typer.Argument(..., help="What was done. Include the literal command when relevant."),
    result: str = typer.Option(..., "--result", help="success | failure | skipped", case_sensitive=False),
    actor: str = typer.Option("agent", "--actor", help="user (operator) or agent (you)", case_sensitive=False),
    notes: str = typer.Option("", "--notes", help="Free-text context: errors, prompts, confirmations."),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        help=f"Group under a session id. Falls back to ${_SESSION_ENV_VAR} when unset.",
    ),
    parent_uuid: Optional[str] = typer.Option(
        None,
        "--parent-uuid",
        help="Causal parent entry's uuid (capture with --print-uuid on the previous log).",
    ),
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="Agent this entry pertains to. Sets the agent_name field so the entry "
             "is reachable via 'clawctl agent audit <name>'.",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress the 'logged -> path' line."),
    print_uuid: bool = typer.Option(
        False,
        "--print-uuid",
        help="On success print only the new entry's uuid (for chaining via --parent-uuid).",
    ),
) -> None:
    if result not in VALID_RESULTS:
        emit_error(
            f"--result must be one of {VALID_RESULTS}",
            hint="Valid values: success, failure, skipped.",
            exit_code=2,
        )
    if actor not in VALID_ACTORS:
        emit_error(
            f"--actor must be one of {VALID_ACTORS}",
            hint="Valid values: user, agent.",
            exit_code=2,
        )

    effective_session = session_id or os.environ.get(_SESSION_ENV_VAR) or None
    entry = _build_entry(
        action=action,
        result=result,
        actor=actor,
        notes=notes,
        session_id=effective_session,
        parent_uuid=parent_uuid,
        agent_name=agent,
    )
    path = _append_entry(entry)

    if print_uuid:
        typer.echo(entry["uuid"])
        return
    if quiet:
        return
    typer.echo(f"logged -> {path}  uuid={entry['uuid'][:8]}")


@audit_app.command(
    "show",
    help="Show / filter audit entries. Requires --agent <name> or --all.",
)
def show(
    date: Optional[str] = typer.Option(None, "--date", help="Restrict to a single UTC day (YYYYMMDD)."),
    actor: Optional[str] = typer.Option(None, "--actor", help="Filter by actor."),
    result: Optional[str] = typer.Option(None, "--result", help="Filter by result."),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Restrict to one session."),
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="Restrict to entries whose agent_name matches. Legacy entries that "
             "pre-date the agent_name field are excluded.",
    ),
    all_flag: bool = typer.Option(
        False,
        "--all",
        help="Show every entry, including legacy/unscoped ones with no agent_name. "
             "Mutually exclusive with --agent.",
    ),
    grep: Optional[str] = typer.Option(None, "--grep", help="Regex matched against action + notes."),
    last: Optional[int] = typer.Option(None, "--last", help="Only the last N matching entries."),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSONL instead of formatted lines."),
) -> None:
    # _require_scope first: scope is the #780 BREAKING contract and
    # the primary gate. An operator who forgot --all/--agent should
    # see that error, not fix a date typo and then discover they
    # still need a scope flag.
    _require_scope(agent, all_flag, verb="show")
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
        agent=agent,
        grep=grep,
        last=last,
    )
    if as_json:
        # ensure_ascii=True per cli/output/_sanitize.py contract — raw
        # non-ASCII codepoints (including bidi overrides smuggled into
        # any field) are escaped to \uXXXX so piping to a terminal is
        # safe even without a downstream sanitize() call.
        for e in entries:
            typer.echo(json.dumps(e, ensure_ascii=True, separators=(",", ":")))
    else:
        for e in entries:
            typer.echo(format_entry(e))


@audit_app.command(
    "tail",
    help="Show the last N entries. Requires --agent <name> or --all.",
)
def tail(
    n: int = typer.Option(20, "-n", "--lines", help="Number of entries to show."),
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="Restrict to entries whose agent_name matches.",
    ),
    all_flag: bool = typer.Option(
        False,
        "--all",
        help="Show every entry, including legacy/unscoped ones.",
    ),
) -> None:
    _require_scope(agent, all_flag, verb="tail")
    entries = filter_entries(
        iter_entries(None),
        actor=None,
        result=None,
        session_id=None,
        agent=agent,
        grep=None,
        last=None,
    )
    for e in entries[-n:]:
        typer.echo(format_entry(e))


@audit_app.command(
    "stats",
    help="Summary counts. Requires --agent <name> or --all.",
)
def stats(
    top: int = typer.Option(10, "--top", help="Top N action groups by frequency."),
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="Restrict the summary to one agent.",
    ),
    all_flag: bool = typer.Option(
        False,
        "--all",
        help="Summarise every entry. Mutually exclusive with --agent.",
    ),
) -> None:
    _require_scope(agent, all_flag, verb="stats")
    actor_count: Counter = Counter()
    result_count: Counter = Counter()
    verb_count: Counter = Counter()
    agent_count: Counter = Counter()
    days: set = set()
    sessions: set = set()
    total = 0
    for e in filter_entries(
        iter_entries(None),
        actor=None,
        result=None,
        session_id=None,
        agent=agent,
        grep=None,
        last=None,
    ):
        total += 1
        # Every Counter key is derived from a disk-read JSONL field
        # and emitted to the terminal via dict repr (which escapes
        # some control bytes but is not bidi-safe) or via raw
        # f-string in the Top-N loop (which is not safe at all).
        # Sanitize at insertion so the emit sites stay simple and
        # no path can leak a smuggled codepoint to the user's shell.
        actor_count[sanitize(str(e.get("actor") or "?"))] += 1
        result_count[sanitize(str(e.get("result") or "?"))] += 1
        verb_count[sanitize(action_verb(str(e.get("action") or "")))] += 1
        agent_count[sanitize(str(e.get("agent_name") or "(unscoped)"))] += 1
        ts = e.get("timestamp")
        if isinstance(ts, str) and len(ts) >= 10:
            days.add(ts[:10])
        sid = e.get("session_id")
        if sid:
            sessions.add(sid)

    typer.echo(f"Total entries:     {total}")
    typer.echo(f"Distinct days:     {len(days)}")
    typer.echo(f"Distinct sessions: {len(sessions)}")
    typer.echo(f"By actor:          {dict(actor_count)}")
    typer.echo(f"By result:         {dict(result_count)}")
    typer.echo(f"By agent:          {dict(agent_count)}")
    if top and verb_count:
        typer.echo(f"Top {top} action groups:")
        for verb, n in verb_count.most_common(top):
            # `verb` is already sanitized at insertion above, but we
            # also coerce `n` to int formatting only — no extra
            # surface here.
            typer.echo(f"  {n:5d}  {verb}")


@audit_app.command("path", help="Print the log directory path.")
def path() -> None:
    typer.echo(str(_log_dir()))


@audit_session_app.command("new", help="Mint a new uuid4 session id and print it.")
def session_new() -> None:
    typer.echo(str(uuidlib.uuid4()))


audit_app.add_typer(audit_session_app, name="session")
