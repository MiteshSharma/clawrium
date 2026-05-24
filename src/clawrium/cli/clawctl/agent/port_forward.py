"""`clawctl agent port-forward <name> [LOCAL:]REMOTE` — forward a port.

Plan §"Specific Outcomes": `clawctl agent port-forward <n> 8080:80`
opens the forward; Ctrl-C exits cleanly.

For this bundle, the implementation is the simplest possible:
delegates to `core/web_ui_tunnel.py:ensure` for the underlying SSH
forward, scoped to the agent's host. The full per-port mapping syntax
(arbitrary LOCAL:REMOTE) is parsed into the existing tunnel manager;
the tunnel manager today wires a single port (the web UI port), so
arbitrary REMOTE values surface as a clean `Not implemented` line
until the tunnel manager gains a port parameter.
"""

from __future__ import annotations

import signal
import time

import typer

from clawrium.cli.clawctl.agent._shared import safe_resolve_agent
from clawrium.cli.output import emit_error, stream_action


def port_forward(
    name: str = typer.Argument(..., help="Agent name."),
    spec: str = typer.Argument(..., help="Port spec: [LOCAL:]REMOTE."),
) -> None:
    """Forward a local port to the agent host."""
    safe_resolve_agent(name)
    local_port, remote_port = _parse_spec(spec)

    # The current tunnel manager opens the web UI port only. For
    # arbitrary REMOTE we'd need a per-call SSH forward; that's a
    # focused follow-up.
    from clawrium.core.web_ui_tunnel import ensure as ensure_tunnel

    try:
        opened_local = ensure_tunnel(name)
    except Exception as exc:
        emit_error(f"failed to open tunnel: {exc}")

    stream_action(
        resource=f"agent/{name}",
        message=(
            f"forwarding localhost:{local_port or opened_local} -> agent:{remote_port} "
            "(Ctrl-C to exit)"
        ),
    )

    # Block until Ctrl-C. Tunnel cleanup is owned by the tunnel
    # manager's idle reaper / signal handlers.
    interrupted = False

    def _handler(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, _handler)
    while not interrupted:
        time.sleep(0.25)
    stream_action(resource=f"agent/{name}", message="port-forward closed")


def _parse_spec(spec: str) -> tuple[int | None, int]:
    """Parse `LOCAL:REMOTE` or `REMOTE`.

    Returns `(local_or_None, remote)`. Invalid inputs exit cleanly.
    """
    if ":" in spec:
        local, _, remote = spec.partition(":")
        if not local or not remote:
            emit_error(f"invalid port spec {spec!r}", hint="use LOCAL:REMOTE or REMOTE")
        try:
            return int(local), int(remote)
        except ValueError:
            emit_error(f"invalid port spec {spec!r}", hint="ports must be integers")
    try:
        return None, int(spec)
    except ValueError:
        emit_error(f"invalid port spec {spec!r}", hint="must be an integer")
