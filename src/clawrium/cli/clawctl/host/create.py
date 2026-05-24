"""`clawctl host create <hostname>` — create a host record.

Plan §4 / §5:

- `--user U` (required) — SSH user
- `--port P` (default 22) — SSH port
- `--alias A` — display alias
- `--bootstrap` — additionally run the host bootstrap playbook
  (legacy `clm host init` equivalent)

Without `--bootstrap`, this just registers the host in `hosts.json`
(idempotent — re-running the same hostname is a no-op if data matches).

Bootstrap is delegated to the legacy `cli/host.py:init` helper for
this bundle because the bootstrap logic intertwines paramiko, host-key
acceptance, and the keypair lifecycle. Extracting that into core is
out of scope for #508; tracked for the bundle-5 cleanup.
"""

from __future__ import annotations

import getpass
from datetime import datetime, timezone
from typing import Optional

import typer

from clawrium.cli.clawctl._common import require_flag
from clawrium.cli.output import emit_error, stream_action
from clawrium.core.hosts import (
    DuplicateHostError,
    HostsFileCorruptedError,
    add_host,
    get_host,
)


def create(
    hostname: str = typer.Argument(..., help="Hostname or IP of the new host."),
    user: Optional[str] = typer.Option(
        None, "--user", "-u", help="SSH user for the host (required)."
    ),
    port: int = typer.Option(22, "--port", "-p", min=1, max=65535, help="SSH port."),
    alias: Optional[str] = typer.Option(
        None, "--alias", "-a", help="Display alias for the host."
    ),
    bootstrap: bool = typer.Option(
        False, "--bootstrap", help="Also run the host bootstrap playbook."
    ),
) -> None:
    """Create a host record (optionally bootstrap remote)."""
    require_flag(user, flag="--user")
    final_user = user or getpass.getuser()

    try:
        existing = get_host(hostname) or (get_host(alias) if alias else None)
    except HostsFileCorruptedError as exc:
        emit_error(str(exc), hint="check ~/.config/clawrium/hosts.json")

    if existing:
        # Idempotent: same hostname + user → no-op success.
        if existing.get("hostname") == hostname and existing.get("user") == final_user:
            stream_action(
                resource=f"host/{alias or hostname}",
                message=f"already exists on {hostname}",
            )
            if bootstrap:
                _run_bootstrap(hostname, final_user)
            return
        emit_error(
            f"host {hostname!r} already registered with different settings",
            hint="clawctl host edit to modify, or clawctl host delete first",
        )

    now = datetime.now(timezone.utc).isoformat()
    record: dict = {
        "hostname": hostname,
        "key_id": hostname,
        "port": port,
        "user": final_user,
        "auth_method": "key",
        "hardware": {},
        "metadata": {"added_at": now, "last_seen": None, "labels": {}},
        "addresses": [
            {
                "address": hostname,
                "is_primary": True,
                "label": None,
                "added_at": now,
            }
        ],
        "agents": {},
    }
    if alias:
        record["alias"] = alias

    try:
        add_host(record)
    except DuplicateHostError as exc:
        emit_error(str(exc), hint="clawctl host delete to remove first")
    except HostsFileCorruptedError as exc:
        emit_error(str(exc), hint="check ~/.config/clawrium/hosts.json")

    display = alias or hostname
    stream_action(resource=f"host/{display}", message=f"created on {hostname}:{port}")

    if bootstrap:
        _run_bootstrap(hostname, final_user)


def _run_bootstrap(hostname: str, user: str) -> None:
    """Delegate bootstrap to the legacy implementation.

    The legacy `clm host init` flow handles keypair generation, SSH
    host-key acceptance, and remote xclm user setup. Re-implementing
    that in this bundle is unnecessary: bundle 5 (#510) collapses the
    legacy module after the audit-after sweep.
    """
    try:
        from clawrium.cli.host import init as _legacy_init
    except ImportError as exc:
        emit_error(
            f"bootstrap unavailable: {exc}",
            hint="re-run without --bootstrap and bootstrap manually",
        )
    stream_action(resource=f"host/{hostname}", message="bootstrapping (legacy path)")
    _legacy_init(hostname=hostname, user=user)
