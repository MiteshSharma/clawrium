"""`clawctl agent chat <name>` — interactive chat session.

Delegates to the existing `cli/chat.py:chat` implementation. The
`--once` flag is exposed as plan §4 requested but, in this bundle, is
informational only: the legacy chat command does not yet expose a
single-shot mode, so `--once "msg"` prints a notice and exits 0. Full
single-shot support is a follow-up.
"""

from __future__ import annotations

from typing import Optional

import typer

from clawrium.cli.clawctl._stub import echo_not_implemented
from clawrium.cli.clawctl.agent._shared import safe_resolve_agent


def chat(
    name: str = typer.Argument(..., help="Agent name."),
    session: str = typer.Option("main", "--session", "-s", help="Gateway session key."),
    timeout: float = typer.Option(
        120.0, "--timeout", min=1.0, help="Response timeout (seconds)."
    ),
    idle_timeout: float = typer.Option(
        300.0, "--idle-timeout", min=0.0, help="Idle timeout (0 disables)."
    ),
    once: Optional[str] = typer.Option(
        None, "--once", help="Send one message and exit (placeholder)."
    ),
) -> None:
    """Start an interactive chat with an agent."""
    safe_resolve_agent(name)  # validates existence
    if once is not None:
        # ATX iter-1 W6: use canonical placeholder so probes match the
        # contract asserted in tests/cli/test_app.py.
        echo_not_implemented("agent", "chat --once")
        return
    from clawrium.cli.chat import chat as _legacy_chat

    _legacy_chat(
        agent_name=name,
        session=session,
        timeout=timeout,
        idle_timeout=idle_timeout,
    )
