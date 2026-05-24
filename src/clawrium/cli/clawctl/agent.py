"""`clawctl agent` — Pattern B target (stub surface for bundle 2).

Real implementation lands in bundles 3-4 (#508, #509). This bundle
only registers the verb surface so `clawctl agent --help` lists the
planned commands from plan §4.
"""

import typer

from clawrium.cli.clawctl._stub import register_stub

__all__ = ["agent_app"]


agent_app = typer.Typer(
    name="agent",
    help="Manage AI assistant instances (agents).",
    no_args_is_help=True,
    add_completion=False,
)


_GROUP = "agent"
_VERBS = (
    ("create", "Install an agent on a host."),
    ("get", "List agents."),
    ("describe", "Describe an agent."),
    ("delete", "Delete an agent."),
    ("edit", "Edit an agent record."),
    ("configure", "Configure an agent non-interactively."),
    ("start", "Start an agent."),
    ("stop", "Stop an agent."),
    ("restart", "Restart an agent."),
    ("sync", "Flush local control-plane state to the agent."),
    ("logs", "Stream agent logs."),
    ("chat", "Chat with an agent."),
    ("open", "Open the agent's web UI in a browser."),
    ("port-forward", "Forward a local port to the agent."),
    ("exec", "Execute a command on the agent host (placeholder)."),
    ("secret", "Manage per-agent secrets."),
    ("memory", "Manage per-agent memory files."),
    ("provider", "Attach/detach providers to/from an agent."),
    ("channel", "Attach/detach channels to/from an agent."),
    ("integration", "Attach/detach integrations to/from an agent."),
    ("skill", "Attach/detach skills to/from an agent."),
    ("registry", "Read-only agent-types catalog."),
)

for _verb, _help in _VERBS:
    register_stub(agent_app, group=_GROUP, verb=_verb, help_text=_help)
