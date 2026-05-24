"""`clawctl provider` — Pattern A attachable (stub surface for bundle 2).

Real implementation lands in bundle 4 (#509). This bundle registers
the nested `registry` subgroup as the only CRUD entrypoint, per plan
§3 / §4.
"""

import typer

from clawrium.cli.clawctl._stub import register_stub

__all__ = ["provider_app"]


provider_app = typer.Typer(
    name="provider",
    help="Inference backend providers (Pattern A attachable).",
    no_args_is_help=True,
    add_completion=False,
)

provider_registry_app = typer.Typer(
    name="registry",
    help="CRUD entrypoint for the provider registry.",
    no_args_is_help=True,
    add_completion=False,
)


_GROUP = "provider registry"
_VERBS = (
    ("create", "Register a provider."),
    ("get", "List registered providers."),
    ("describe", "Describe a provider."),
    ("delete", "Delete a provider."),
    ("edit", "Edit a provider."),
    ("refresh", "Refresh provider models / metadata."),
)

for _verb, _help in _VERBS:
    register_stub(provider_registry_app, group=_GROUP, verb=_verb, help_text=_help)

provider_app.add_typer(provider_registry_app, name="registry")
