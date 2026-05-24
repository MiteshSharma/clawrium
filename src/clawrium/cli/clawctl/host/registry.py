"""`clawctl host registry get|describe` — read-only host-types catalog.

Plan §"Specific Outcomes": placeholder content + exit 0. There is no
formal "host type" registry today (every host is a generic SSH target);
this verb exists so the surface matches kubectl-style symmetry across
Pattern-B nouns and tools that ask `--help` for a list of supported
host profiles get a clean response rather than an unknown-command
error.
"""

from __future__ import annotations

import typer

from clawrium.cli.output import render_table

__all__ = ["registry_app"]


registry_app = typer.Typer(
    name="registry",
    help="Read-only catalog of supported host profiles.",
    no_args_is_help=True,
    add_completion=False,
)


_PROFILES = [
    {
        "name": "generic-ssh",
        "description": "Any SSH-reachable Linux machine (default).",
    },
]


@registry_app.command("get")
def get() -> None:
    """List supported host profiles."""
    headers = ["NAME", "DESCRIPTION"]
    body = [[p["name"], p["description"]] for p in _PROFILES]
    typer.echo(render_table(headers, body), nl=False)


@registry_app.command("describe")
def describe(
    profile: str = typer.Argument(..., help="Profile name to describe."),
) -> None:
    """Describe a host profile."""
    for entry in _PROFILES:
        if entry["name"] == profile:
            typer.echo(f"Name:         {entry['name']}")
            typer.echo(f"Description:  {entry['description']}")
            return
    typer.echo(f"Profile {profile!r} not found.")
    raise typer.Exit(code=1)
