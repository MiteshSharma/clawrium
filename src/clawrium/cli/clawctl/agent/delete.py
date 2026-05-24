"""`clawctl agent delete <name>` — remove an agent.

Runs the remote cleanup playbook via `core/lifecycle.py:remove_agent`
then prunes the local record via `core/hosts.py:remove_agent_from_host`.
"""

from __future__ import annotations

import typer

from clawrium.cli.clawctl._common import confirm_destructive
from clawrium.cli.clawctl.agent._shared import safe_resolve_agent
from clawrium.cli.output import emit_error, stream_action
from clawrium.core.hosts import remove_agent_from_host
from clawrium.core.lifecycle import LifecycleError, remove_agent


def delete(
    name: str = typer.Argument(..., help="Agent name."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirm prompt."),
) -> None:
    """Delete an agent (remote cleanup + local record removal)."""
    host, agent_key, claw_record = safe_resolve_agent(name)
    confirm_destructive(
        prompt=f"Delete agent '{name}'? Removes remote state and local record.",
        yes=yes,
    )

    hostname = host["hostname"]
    agent_type = claw_record.get("type", agent_key)

    def on_event(stage: str, message: str) -> None:
        stream_action(resource=f"agent/{name}", message=f"[{stage}] {message}")

    try:
        remove_agent(
            hostname=hostname,
            claw_name=agent_type,
            agent_name=agent_key,
            on_event=on_event,
        )
    except LifecycleError as exc:
        emit_error(f"remote cleanup failed: {exc}")

    if not remove_agent_from_host(hostname, agent_key):
        emit_error(
            f"failed to remove local record for {name!r}",
            hint="check ~/.config/clawrium/hosts.json",
        )
    stream_action(resource=f"agent/{name}", message="deleted")
