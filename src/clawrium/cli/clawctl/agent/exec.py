"""`clawctl agent exec <name> -- <cmd>` — placeholder per plan §4.

Plan §"Specific Outcomes": prints `Not implemented: agent exec` and
exits 0.
"""

from __future__ import annotations

from typing import Optional

import typer

from clawrium.cli.clawctl._stub import echo_not_implemented


def exec_cmd(
    name: str = typer.Argument(..., help="Agent name."),
    cmd: Optional[list[str]] = typer.Argument(
        None, help="Command to execute (after `--`)."
    ),
) -> None:
    """Execute a command on the agent host (placeholder; exits 0)."""
    # Silence unused warnings; the surface accepts the args so help
    # text and parsing match plan §4.
    _ = (name, cmd)
    echo_not_implemented("agent", "exec")
