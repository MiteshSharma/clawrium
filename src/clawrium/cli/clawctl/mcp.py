"""`clawctl mcp` — Pattern A attachable (PLACEHOLDER; bundle 2 stub).

Per plan §4 the entire `mcp` group is a placeholder for now. Bundle 4
keeps it as a placeholder pending a separate MCP design.
"""

import typer

from clawrium.cli.clawctl._stub import register_stub

__all__ = ["mcp_app"]


mcp_app = typer.Typer(
    name="mcp",
    help="MCP servers (Pattern A attachable; placeholder).",
    no_args_is_help=True,
    add_completion=False,
)

mcp_registry_app = typer.Typer(
    name="registry",
    help="Read-only entrypoint for the MCP registry (placeholder).",
    no_args_is_help=True,
    add_completion=False,
)


_GROUP = "mcp registry"
_VERBS = (
    ("get", "List registered MCP servers."),
    ("describe", "Describe an MCP server."),
)

for _verb, _help in _VERBS:
    register_stub(mcp_registry_app, group=_GROUP, verb=_verb, help_text=_help)

mcp_app.add_typer(mcp_registry_app, name="registry")
