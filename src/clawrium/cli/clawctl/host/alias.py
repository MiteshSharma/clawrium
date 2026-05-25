"""`clawctl host alias <hostname>` — multi-value alias management.

Plan §4: a host can have many aliases; this verb is the multi-value
manager, not the rename verb (rename is `edit --alias`).

Flags are mutually exclusive: `--add`, `--remove`, `--list`. Adds and
removes can repeat to operate on multiple values in one call.

The data model: legacy hosts.py stores a single `alias`. To support
multiple aliases without touching core, we read/write a new field
`aliases: list[str]` alongside it. When `--add` is called and only
the legacy `alias` is set, we promote it into `aliases` first.
"""

from __future__ import annotations

from typing import Optional

import typer

from clawrium.cli.clawctl._common import validate_alias
from clawrium.cli.clawctl.host._shared import display_name, hostname_key, safe_get_host
from clawrium.cli.output import emit_error, render_table, stream_action
from clawrium.core.hosts import alias_exists, update_host


def alias(
    hostname: str = typer.Argument(..., help="Host name or current alias."),
    add: Optional[list[str]] = typer.Option(
        None, "--add", help="Alias to add. Repeatable."
    ),
    remove: Optional[list[str]] = typer.Option(
        None, "--remove", help="Alias to remove. Repeatable."
    ),
    list_aliases: bool = typer.Option(False, "--list", help="List the host's aliases."),
) -> None:
    """Manage aliases for a host (add/remove/list)."""
    host = safe_get_host(hostname)
    canonical = hostname_key(host)
    name = display_name(host)

    actions = sum(bool(x) for x in (add, remove, list_aliases))
    if actions == 0:
        emit_error(
            "no action requested",
            hint="pass --add, --remove, or --list",
        )
    if list_aliases and (add or remove):
        emit_error("--list cannot be combined with --add or --remove")

    if list_aliases:
        current = _read_aliases(host)
        typer.echo(render_table(["ALIAS"], [[a] for a in current]), nl=False)
        return

    if add:
        for value in add:
            # Positive-whitelist + bidi rejection (ATX iter-1 W10, S1).
            validate_alias(value)
            exists, conflict = alias_exists(value, exclude_hostname=canonical)
            if exists:
                emit_error(
                    f"alias {value!r} already in use by {conflict!r}",
                    hint="remove the conflict first",
                )

    def apply(h: dict) -> dict:
        current = _read_aliases(h)
        if add:
            for value in add:
                if value not in current:
                    current.append(value)
        if remove:
            current = [a for a in current if a not in remove]
        h["aliases"] = current
        # Keep the legacy `alias` pointing at the first entry for
        # backwards-compat with `core/hosts.py:get_host`.
        h["alias"] = current[0] if current else None
        return h

    if not update_host(canonical, apply):
        emit_error(f"failed to update aliases for {name!r}")
    stream_action(resource=f"host/{name}", message="aliases updated")


def _read_aliases(host: dict) -> list[str]:
    explicit = host.get("aliases") or []
    if explicit:
        return list(explicit)
    legacy = host.get("alias")
    return [legacy] if legacy else []
