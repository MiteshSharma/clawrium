"""`clawctl integration` — Pattern A attachable (stub for bundle 2).

Real implementation lands in bundle 4 (#509).
"""

import typer

from clawrium.cli.clawctl._stub import register_stub

__all__ = ["integration_app"]


integration_app = typer.Typer(
    name="integration",
    help="External service integrations (Pattern A attachable).",
    no_args_is_help=True,
    add_completion=False,
)

integration_registry_app = typer.Typer(
    name="registry",
    help="CRUD entrypoint for the integration registry.",
    no_args_is_help=True,
    add_completion=False,
)


_GROUP = "integration registry"
_VERBS = (
    ("create", "Register an integration."),
    ("get", "List registered integrations."),
    ("describe", "Describe an integration."),
    ("delete", "Delete an integration."),
    ("edit", "Edit an integration."),
)

for _verb, _help in _VERBS:
    register_stub(integration_registry_app, group=_GROUP, verb=_verb, help_text=_help)

integration_app.add_typer(integration_registry_app, name="registry")
