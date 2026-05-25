"""`clawctl agent edit <name>` — open the agent's YAML record in $EDITOR.

For this bundle, we provide the surface and a clear `[NOT IMPLEMENTED]`
exit so the help text + flag parsing work. The full $EDITOR flow lands
in bundle 4 (#509), where it shares infrastructure with `clawctl
provider registry edit` and friends.
"""

from __future__ import annotations

import typer

from clawrium.cli.clawctl._stub import echo_not_implemented
from clawrium.cli.clawctl.agent._shared import safe_resolve_agent


def edit(
    name: str = typer.Argument(..., help="Agent name."),
) -> None:
    """Open the agent record in $EDITOR (placeholder for bundle 3)."""
    # ATX iter-1 W6: every placeholder must use the canonical
    # `echo_not_implemented` so scripts probing for the standard string
    # see consistent output across the surface.
    safe_resolve_agent(name)  # validates the agent exists
    echo_not_implemented("agent", "edit")
