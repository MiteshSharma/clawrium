"""`clawctl host reset <hostname>` — wipe remote xclm state.

Distinct from `delete`: `reset` keeps the local host record but
removes all clawrium-managed state (services, users, paths) on the
remote machine via the existing `core/reset.py` flow.

Non-interactive contract: `--yes` is required on non-TTY stdin; TTY
gets a confirm prompt by default.
"""

from __future__ import annotations

from datetime import datetime, timezone

import typer

from clawrium.cli.clawctl._common import confirm_destructive
from clawrium.cli.clawctl.host._shared import display_name, hostname_key, safe_get_host
from clawrium.cli.output import emit_error, stream_action
from clawrium.core.hosts import update_host
from clawrium.core.reset import enumerate_targets, execute_reset


def reset(
    hostname: str = typer.Argument(..., help="Host name or alias to reset."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirm prompt."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be removed and exit."
    ),
) -> None:
    """Wipe clawrium-managed state on a remote host. Local record is kept."""
    host = safe_get_host(hostname)
    name = display_name(host)
    canonical = hostname_key(host)

    try:
        targets = enumerate_targets(canonical)
    except Exception as exc:  # core.reset raises a variety of errors
        emit_error(f"failed to enumerate reset targets: {exc}")

    # ATX iter-1 S3: confirm BEFORE printing the "would remove" summary
    # on the destructive (non-dry-run) path. Previously the summary
    # appeared before the guard fired, which read as if the action was
    # already proceeding.
    if dry_run:
        stream_action(
            resource=f"host/{name}",
            message=(
                f"would remove users={len(targets.users)} "
                f"services={len(targets.services)} paths={len(targets.paths)}"
            ),
        )
        return

    confirm_destructive(
        prompt=(
            f"Wipe clawrium state on '{name}'? "
            "Removes services, users, and managed paths."
        ),
        yes=yes,
    )
    stream_action(
        resource=f"host/{name}",
        message=(
            f"removing users={len(targets.users)} "
            f"services={len(targets.services)} paths={len(targets.paths)}"
        ),
    )

    try:
        result = execute_reset(canonical, targets)
    except Exception as exc:
        emit_error(f"reset failed: {exc}")

    if not result.success:
        emit_error(
            f"reset failed on {name}",
            hint="re-run with --dry-run to inspect targets",
        )

    def clear_agents(h: dict) -> dict:
        h["agents"] = {}
        meta = h.setdefault("metadata", {})
        meta["last_reset"] = datetime.now(timezone.utc).isoformat()
        return h

    update_host(canonical, clear_agents)
    removed = result.removed
    stream_action(
        resource=f"host/{name}",
        message=(
            f"reset complete (users={removed.get('users', 0)} "
            f"services={removed.get('services', 0)} "
            f"paths={removed.get('paths', 0)})"
        ),
    )
