"""`clawctl agent edit <name>` — open the agent's YAML record in $EDITOR.

For this bundle, we provide the surface and a clear `[NOT IMPLEMENTED]`
exit so the help text + flag parsing work. The full $EDITOR flow lands
in bundle 4 (#509), where it shares infrastructure with `clawctl
provider registry edit` and friends.
"""

from __future__ import annotations

import typer

from clawrium.cli.clawctl.agent._shared import safe_resolve_agent
from clawrium.cli.output import stream_action


def edit(
    name: str = typer.Argument(..., help="Agent name."),
) -> None:
    """Open the agent record in $EDITOR (placeholder for bundle 3)."""
    safe_resolve_agent(name)  # validates the agent exists
    stream_action(
        resource=f"agent/{name}",
        message="edit in $EDITOR — not yet implemented (bundle 4)",
    )
    raise typer.Exit(code=0)
