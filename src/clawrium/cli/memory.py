"""Memory management commands for openclaw agents.

Surfaces ``clm agent <name> memory show|delete``. Thin layer over
``clawrium.core.memory`` — argument parsing, confirmation flows, and
human-readable rendering.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from clawrium.core.memory import (
    delete_memory_files,
    get_memory_info,
)
from clawrium.core.hosts import get_host
from clawrium.core.secrets import (
    AgentNotFoundError,
    get_installed_claw,
)

__all__ = ["memory_app", "show_cmd", "delete_cmd"]

console = Console()

memory_app = typer.Typer(
    name="memory",
    help="Inspect and manage memory for openclaw agents",
    no_args_is_help=True,
)


def _human_size(num_bytes: int) -> str:
    """Render an integer byte count as B / KB / MB. One decimal place."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def _resolve_openclaw_for_cli(claw_name: str) -> tuple[str, str]:
    """Resolve agent name to (hostname, unix_agent_name) or exit 1.

    Restricts memory ops to openclaw agents — other types are not
    supported in this iteration. Returns the unix-level ``agent_name``
    the core module needs.
    """
    try:
        hostname, agent_key, name = get_installed_claw(claw_name)
    except AgentNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    # get_installed_claw returns the agents-dict key as the second element,
    # which under the current schema is the agent name rather than the claw
    # type. Read the inner type field from the host record to validate.
    host = get_host(hostname)
    record = (host or {}).get("agents", {}).get(agent_key, {})
    actual_type = record.get("type") if isinstance(record, dict) else None

    if actual_type != "openclaw":
        console.print(
            f"[red]Error:[/red] memory is only supported for openclaw agents "
            f"(got '{actual_type or 'unknown'}')."
        )
        raise typer.Exit(code=1)

    return hostname, name


@memory_app.command(name="show")
def show_cmd(
    claw_name: str = typer.Argument(..., help="Agent instance name"),
) -> None:
    """Show memory file paths and sizes for an openclaw agent."""
    hostname, agent_name = _resolve_openclaw_for_cli(claw_name)

    info = get_memory_info(hostname, agent_name)
    if info is None:
        console.print(
            f"[yellow]Memory unavailable for '{claw_name}' on '{hostname}'.[/yellow]"
        )
        console.print(
            "[dim]The agent may be unreachable, still installing, or in a "
            "failed state. Run 'clm ps' to check status.[/dim]"
        )
        raise typer.Exit(code=1)

    console.print(f"\n[bold]Agent:[/bold] {claw_name} ({hostname})")
    console.print(f"[bold]Workspace:[/bold] {info['workspace_path']}")
    console.print(f"[bold]Total size:[/bold] {_human_size(info['total_bytes'])}\n")

    table = Table(show_header=True, box=None)
    table.add_column("File", style="cyan")
    table.add_column("Status")
    table.add_column("Size", justify="right")

    if not info["files"]:
        console.print("  No memory files.")
        return

    for entry in info["files"]:
        if entry["exists"]:
            status = "[green]present[/green]"
            size = _human_size(entry["size_bytes"])
        else:
            status = "[dim]missing[/dim]"
            size = "-"
        table.add_row(entry["relative_path"], status, size)

    console.print(table)


def _existing_files(hostname: str, agent_name: str) -> list[str] | None:
    """Return relative paths of all existing memory files, or None on miss."""
    info = get_memory_info(hostname, agent_name)
    if info is None:
        return None
    return [f["relative_path"] for f in info["files"] if f["exists"]]


@memory_app.command(name="delete")
def delete_cmd(
    claw_name: str = typer.Argument(..., help="Agent instance name"),
    file: str | None = typer.Option(
        None,
        "--file",
        "-f",
        help="Single memory file to delete (e.g., SOUL.md or memory/2026-05-09.md).",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        help="Delete every memory file. Requires --force and a typed confirmation.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip the per-file confirmation prompt. Required for --all.",
    ),
) -> None:
    """Delete one memory file or every memory file for the agent.

    --all is gated by --force AND a typed agent-name confirmation so a
    bulk wipe cannot happen by accident or by piped input.
    """
    if not file and not all_files:
        console.print(
            "[red]Error:[/red] specify either --file <name> or --all."
        )
        raise typer.Exit(code=1)
    if file and all_files:
        console.print(
            "[red]Error:[/red] --file and --all are mutually exclusive."
        )
        raise typer.Exit(code=1)

    hostname, agent_name = _resolve_openclaw_for_cli(claw_name)

    if all_files:
        if not force:
            console.print(
                "[red]Error:[/red] --all requires --force to acknowledge "
                "the bulk delete."
            )
            raise typer.Exit(code=1)

        targets = _existing_files(hostname, agent_name)
        if targets is None:
            console.print(
                f"[yellow]Memory unavailable for '{claw_name}'.[/yellow] "
                "Cannot enumerate files to delete."
            )
            raise typer.Exit(code=1)
        if not targets:
            console.print("No memory files to delete.")
            raise typer.Exit(code=0)

        console.print(
            f"[yellow]About to delete {len(targets)} memory file(s) "
            f"from '{claw_name}'.[/yellow]"
        )
        for path in targets:
            console.print(f"  - {path}")

        typed = typer.prompt(
            f"Type the agent name '{claw_name}' to confirm",
            default="",
            show_default=False,
        )
        if typed.strip() != claw_name:
            console.print("Cancelled.")
            raise typer.Exit(code=1)

        ok, err = delete_memory_files(hostname, agent_name, targets)
    else:
        if not force:
            confirmed = typer.confirm(
                f"Delete '{file}' from '{claw_name}'? This cannot be undone."
            )
            if not confirmed:
                console.print("Cancelled.")
                raise typer.Exit(code=0)

        ok, err = delete_memory_files(hostname, agent_name, [file])

    if not ok:
        console.print(f"[red]Error:[/red] {err}")
        raise typer.Exit(code=1)

    if all_files:
        console.print(
            f"[green]Deleted {len(targets)} memory file(s) from "
            f"'{claw_name}'.[/green]"
        )
    else:
        console.print(f"[green]Deleted '{file}' from '{claw_name}'.[/green]")
