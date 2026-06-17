#!/usr/bin/env python3
# clawctl-audit — append and query the clawctl operator audit trail.
#
# The audit trail is the operator-side record of every mutating clawctl
# operation performed by a human operator or by an AI assistant using the
# /clawctl skill. It is intended as a full trace of everything that
# happens on an agent's control machine via that skill.
#
# Storage layout
#   $XDG_CONFIG_HOME/clawrium/changelog/<YYYYMMDD>.jsonl
#   (defaults to ~/.config/clawrium/changelog/)
#
#   One file per UTC day, append-only, one JSON object per line.
#
# Schema v1 fields (every entry written by `clawctl-audit log`):
#   type        -- discriminator; "clawctl_command" for the standard shape
#   uuid        -- stable per-entry id (uuid4)
#   parent_uuid -- optional causal parent (currently always null; reserved)
#   session_id  -- optional grouping id from $CLAWCTL_AUDIT_SESSION_ID (null otherwise)
#   timestamp   -- ISO 8601 UTC with millisecond precision (e.g. "2026-06-17T18:23:00.123Z")
#   cwd         -- captured os.getcwd() at write time
#   version     -- {"audit": "<schema-int>", "tool": "<clawctl-audit ver>", "clawctl": "<detected ver|null>"}
#   actor       -- "user" or "agent"
#   action      -- short description / literal command run
#   result      -- "success" | "failure" | "skipped"
#   notes       -- free-text context; "" allowed
#
# Reads are tolerant of legacy entries that predate any of these fields.
#
# The CLI is intentionally stdlib-only so it has no install-time
# dependencies and can be dropped onto any Python 3.8+ machine.

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid as uuidlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ACTORS = ("user", "agent")
VALID_RESULTS = ("success", "failure", "skipped")
DEFAULT_TYPE = "clawctl_command"
SCHEMA_VERSION = "1"
TOOL_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Storage layout
# ---------------------------------------------------------------------------

def config_root() -> Path:
    """Return the clawrium config root.

    Honours $XDG_CONFIG_HOME when set (Linux convention), otherwise falls
    back to ~/.config. Lets callers override via $CLAWRIUM_CONFIG_HOME for
    test isolation.
    """
    override = os.environ.get("CLAWRIUM_CONFIG_HOME")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "clawrium"


def log_dir() -> Path:
    return config_root() / "changelog"


def log_path_for(dt: datetime) -> Path:
    return log_dir() / f"{dt.strftime('%Y%m%d')}.jsonl"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso_ms() -> str:
    """ISO 8601 UTC with millisecond precision, e.g. ``2026-06-17T18:23:00.123Z``.

    `datetime.isoformat` gives microseconds; we trim to ms to match the
    Claude Code convention and avoid a misleading precision claim.
    """
    now = utc_now()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def detect_clawctl_version() -> Optional[str]:
    """Best-effort: ask `clawctl version` for the installed CLI version.

    Returns the bare semver-ish string (e.g. ``26.6.3``) or ``None`` if the
    binary is missing or its output is unparseable. Never raises.
    """
    binary = shutil.which("clawctl")
    if not binary:
        return None
    try:
        out = subprocess.run(
            [binary, "version"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    # `clawctl version` prints something like `clawctl 26.6.3`
    tokens = out.stdout.strip().split()
    if len(tokens) >= 2:
        return tokens[1]
    return None


# ---------------------------------------------------------------------------
# Read / write primitives
# ---------------------------------------------------------------------------

def build_entry(
    *,
    action: str,
    result: str,
    actor: str,
    notes: str = "",
    session_id: Optional[str] = None,
    parent_uuid: Optional[str] = None,
    entry_type: str = DEFAULT_TYPE,
) -> dict:
    return {
        "type": entry_type,
        "uuid": str(uuidlib.uuid4()),
        "parent_uuid": parent_uuid,
        "session_id": session_id,
        "timestamp": utc_now_iso_ms(),
        "cwd": os.getcwd(),
        "version": {
            "audit": SCHEMA_VERSION,
            "tool": TOOL_VERSION,
            "clawctl": detect_clawctl_version(),
        },
        "actor": actor,
        "action": action,
        "result": result,
        "notes": notes or "",
    }


def append_entry(entry: dict) -> Path:
    target = log_path_for(utc_now())
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
    root = log_dir()
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


def format_entry(e: dict) -> str:
    notes = e.get("notes") or ""
    tail = f"  -- {notes}" if notes else ""
    sess = e.get("session_id")
    sess_tag = f" {sess[:8]}" if sess else ""
    return (
        f"{e.get('timestamp', '?'):24s}  "
        f"[{e.get('actor', '?'):5s}]  "
        f"{e.get('result', '?'):7s}  "
        f"{e.get('action', '?')}{sess_tag}{tail}"
    )


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_log(args: argparse.Namespace) -> int:
    session_id = args.session_id or os.environ.get("CLAWCTL_AUDIT_SESSION_ID") or None
    entry = build_entry(
        action=args.action,
        result=args.result,
        actor=args.actor,
        notes=args.notes,
        session_id=session_id,
        parent_uuid=args.parent_uuid,
    )
    path = append_entry(entry)
    if args.print_uuid:
        # Stable-handle UUID for the caller to use as a parent_uuid on the
        # next entry in a chain. Goes to stdout (one line, no other output).
        print(entry["uuid"])
        return 0
    if args.quiet:
        return 0
    print(f"logged -> {path}  uuid={entry['uuid'][:8]}")
    return 0


def _apply_filters(entries, args) -> list:
    out = list(entries)
    if args.actor:
        out = [e for e in out if e.get("actor") == args.actor]
    if args.result:
        out = [e for e in out if e.get("result") == args.result]
    if args.session_id:
        out = [e for e in out if e.get("session_id") == args.session_id]
    if args.grep:
        pat = re.compile(args.grep)
        def matches(e: dict) -> bool:
            haystack = " ".join([
                str(e.get("action", "")),
                str(e.get("notes", "")),
            ])
            return bool(pat.search(haystack))
        out = [e for e in out if matches(e)]
    if args.last:
        out = out[-args.last :]
    return out


def cmd_show(args: argparse.Namespace) -> int:
    entries = _apply_filters(iter_entries(args.date), args)
    if args.json:
        for e in entries:
            print(json.dumps(e, ensure_ascii=False, separators=(",", ":")))
    else:
        for e in entries:
            print(format_entry(e))
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    entries = list(iter_entries(None))[-args.n :]
    for e in entries:
        print(format_entry(e))
    return 0


def action_verb(action: str) -> str:
    """Return a useful coarse grouping for an action string.

    Almost every action will start with ``clawctl``, so the leading token
    alone is uninformative. We use the first two tokens when the action
    begins with ``clawctl`` (e.g. ``clawctl agent``, ``clawctl host``), which
    captures the command group — the level of granularity an operator
    typically wants in a summary.
    """
    if not action:
        return "?"
    tokens = action.split()
    if tokens and tokens[0] == "clawctl" and len(tokens) >= 2:
        return f"clawctl {tokens[1]}"
    return tokens[0]


def cmd_stats(args: argparse.Namespace) -> int:
    actor_count: Counter = Counter()
    result_count: Counter = Counter()
    verb_count: Counter = Counter()
    days = set()
    sessions = set()
    total = 0
    for e in iter_entries(None):
        total += 1
        actor_count[e.get("actor", "?")] += 1
        result_count[e.get("result", "?")] += 1
        verb_count[action_verb(e.get("action", "") or "")] += 1
        ts = e.get("timestamp", "")
        if len(ts) >= 10:
            days.add(ts[:10])
        sid = e.get("session_id")
        if sid:
            sessions.add(sid)

    print(f"Total entries:    {total}")
    print(f"Distinct days:    {len(days)}")
    print(f"Distinct sessions: {len(sessions)}")
    print(f"By actor:         {dict(actor_count)}")
    print(f"By result:        {dict(result_count)}")
    if args.top and verb_count:
        print(f"Top {args.top} action groups:")
        for verb, n in verb_count.most_common(args.top):
            print(f"  {n:5d}  {verb}")
    return 0


def cmd_path(_: argparse.Namespace) -> int:
    """Print the log directory path. Useful for shell automation."""
    print(log_dir())
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    """Mint a new session id and print it.

    Idea: a workflow does ``export CLAWCTL_AUDIT_SESSION_ID="$(clawctl-audit session new)"``
    before kicking off a series of commands. Every subsequent ``log`` picks
    that env var up and tags the entry with it.
    """
    if args.cmd_session == "new":
        print(str(uuidlib.uuid4()))
        return 0
    return 1


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clawctl-audit",
        description="Append and query the clawctl operator audit trail.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"clawctl-audit {TOOL_VERSION} (schema v{SCHEMA_VERSION})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_log = sub.add_parser(
        "log",
        help="Append an entry to today's log",
        description="Append a single JSONL entry to ~/.config/clawrium/changelog/<UTC-date>.jsonl",
    )
    p_log.add_argument("action", help="What was done. Include the literal command when relevant.")
    p_log.add_argument("--result", required=True, choices=VALID_RESULTS)
    p_log.add_argument("--actor", choices=VALID_ACTORS, default="agent")
    p_log.add_argument("--notes", default="", help="Free-text context — errors, confirmations, etc.")
    p_log.add_argument(
        "--session-id",
        dest="session_id",
        help="Group this entry under a session id (overrides $CLAWCTL_AUDIT_SESSION_ID)",
    )
    p_log.add_argument(
        "--parent-uuid",
        dest="parent_uuid",
        help="Causal parent entry's uuid (use 'clawctl-audit log --print-uuid' to capture it)",
    )
    p_log.add_argument("--quiet", "-q", action="store_true", help="Suppress the 'logged -> path' line")
    p_log.add_argument(
        "--print-uuid",
        action="store_true",
        help="On success print only the new entry's uuid (for piping into --parent-uuid of a follow-up entry)",
    )
    p_log.set_defaults(func=cmd_log)

    p_show = sub.add_parser("show", help="Show / filter audit entries")
    p_show.add_argument("--date", help="Restrict to a single UTC day (YYYYMMDD)")
    p_show.add_argument("--actor", choices=VALID_ACTORS)
    p_show.add_argument("--result", choices=VALID_RESULTS)
    p_show.add_argument("--session-id", dest="session_id", help="Restrict to one session")
    p_show.add_argument("--grep", help="Regex matched against action + notes")
    p_show.add_argument("--last", type=int, help="Only the last N matching entries")
    p_show.add_argument("--json", action="store_true", help="Emit raw JSONL instead of formatted lines")
    p_show.set_defaults(func=cmd_show)

    p_tail = sub.add_parser("tail", help="Show the last N entries across all days")
    p_tail.add_argument("-n", type=int, default=20)
    p_tail.set_defaults(func=cmd_tail)

    p_stats = sub.add_parser("stats", help="Summary counts across the full audit history")
    p_stats.add_argument("--top", type=int, default=10, help="Top N action groups by frequency")
    p_stats.set_defaults(func=cmd_stats)

    p_path = sub.add_parser("path", help="Print the log directory path")
    p_path.set_defaults(func=cmd_path)

    p_session = sub.add_parser("session", help="Manage session ids")
    sess_sub = p_session.add_subparsers(dest="cmd_session", required=True)
    sess_sub.add_parser("new", help="Mint a new uuid4 session id and print it")
    p_session.set_defaults(func=cmd_session)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
