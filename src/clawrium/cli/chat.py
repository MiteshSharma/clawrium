"""Interactive chat command for OpenClaw agents."""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape as rich_escape

from clawrium.core.chat import (
    ChatAuthenticationError,
    ChatConnectionError,
    ChatProtocolError,
    OpenClawChatClient,
)
from clawrium.core.hosts import get_agent_by_name, HostsFileCorruptedError

console = Console()

__all__ = ["chat"]


def chat(
    agent_name: str = typer.Argument(..., help="Installed agent name to chat with"),
    session: str = typer.Option("main", "--session", "-s", help="Gateway session key"),
) -> None:
    """Start an interactive chat session with an installed agent."""
    try:
        resolved = get_agent_by_name(agent_name)
    except HostsFileCorruptedError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {rich_escape(str(exc))}")
        raise typer.Exit(code=1)

    if not resolved:
        console.print(f"[red]Error:[/red] Agent '{rich_escape(agent_name)}' not found")
        console.print("Run 'clm ps' to list installed agents.")
        raise typer.Exit(code=1)

    host_record, agent_type, agent_record = resolved
    if agent_type != "openclaw":
        console.print(
            f"[red]Error:[/red] Chat is currently supported for OpenClaw only (got {rich_escape(agent_type)})"
        )
        raise typer.Exit(code=1)

    try:
        gateway = _extract_gateway_config(agent_record)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {rich_escape(str(exc))}")
        raise typer.Exit(code=1)
    gateway_url = gateway["url"]
    auth_token = gateway["auth"]

    display_host = (
        host_record.get("alias") or host_record.get("hostname") or "unknown-host"
    )
    display_agent = (
        agent_record.get("agent_name")
        or agent_record.get("name")
        or agent_name
        or "openclaw"
    )

    console.print(
        f"[green]Connected target:[/green] {rich_escape(str(display_agent))} on {rich_escape(str(display_host))}"
    )
    console.print("Type /exit or press Ctrl+D to end the chat session.")

    try:
        asyncio.run(
            _chat_loop(
                gateway_url=str(gateway_url),
                auth_token=str(auth_token),
                session_key=session,
            )
        )
    except (ChatConnectionError, ChatAuthenticationError, ChatProtocolError) as exc:
        console.print(f"[red]Chat failed:[/red] {rich_escape(str(exc))}")
        raise typer.Exit(code=1)


async def _chat_loop(gateway_url: str, auth_token: str, session_key: str) -> None:
    client = OpenClawChatClient(gateway_url=gateway_url, auth_token=auth_token)
    await client.connect()

    try:
        while True:
            try:
                user_input = await asyncio.to_thread(input, "you> ")
            except EOFError:
                console.print("\n[dim]Chat ended.[/dim]")
                break
            except KeyboardInterrupt:
                console.print("\n[dim]Interrupted.[/dim]")
                break

            message = user_input.strip()
            if not message:
                continue
            if message in {"/exit", "/quit"}:
                console.print("[dim]Bye.[/dim]")
                break

            shown_prefix = False

            def on_delta(delta: str) -> None:
                nonlocal shown_prefix
                if not shown_prefix:
                    print("agent> ", end="", flush=True)
                    shown_prefix = True
                print(delta, end="", flush=True)

            final_text = await client.send_message(
                message=message,
                session_key=session_key,
                on_delta=on_delta,
            )
            if shown_prefix:
                print()
            elif final_text:
                print(f"agent> {final_text}")
            else:
                print("agent> [no response]")
    finally:
        await client.close()


def _extract_gateway_config(agent_record: dict[str, Any]) -> dict[str, str]:
    config = agent_record.get("config")
    if not isinstance(config, dict):
        raise ValueError("Agent config missing. Re-run agent configure/install.")

    gateway = config.get("gateway")
    if not isinstance(gateway, dict):
        raise ValueError("Gateway config missing. Re-run agent configure/install.")

    gateway_url = gateway.get("url")
    if not isinstance(gateway_url, str) or not gateway_url.strip():
        raise ValueError(
            "Gateway URL is missing. Re-run install/configure to capture gateway URL."
        )

    auth_token = gateway.get("auth")
    if not isinstance(auth_token, str) or not auth_token.strip():
        raise ValueError(
            "Gateway auth token is missing. Re-run install/configure to refresh pairing token."
        )

    return {"url": gateway_url, "auth": auth_token}
