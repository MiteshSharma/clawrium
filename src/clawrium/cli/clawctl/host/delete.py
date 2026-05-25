"""`clawctl host delete <hostname>` — remove a host record.

Non-interactive contract:
- `--yes` → proceed silently.
- TTY stdin + no `--yes` → confirm prompt; decline aborts exit 0.
- Non-TTY stdin + no `--yes` → fail fast (Error + Hint).
"""

from __future__ import annotations

import typer

from clawrium.cli.clawctl._common import confirm_destructive
from clawrium.cli.clawctl.host._shared import display_name, hostname_key, safe_get_host
from clawrium.cli.output import emit_error, stream_action
from clawrium.core.hosts import remove_host
from clawrium.core.keys import delete_host_keys


def delete(
    hostname: str = typer.Argument(..., help="Host name or alias to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirm prompt."),
) -> None:
    """Delete a host record (and its keypair). Use --yes to skip prompt."""
    host = safe_get_host(hostname)
    name = display_name(host)
    confirm_destructive(
        prompt=f"Delete host '{name}'? This removes its local record.",
        yes=yes,
    )

    canonical = hostname_key(host)
    removed = remove_host(canonical)
    if not removed:
        emit_error(f"failed to remove host {name!r}")
    key_id = host.get("key_id") or canonical
    delete_host_keys(key_id)
    stream_action(resource=f"host/{name}", message="deleted")
