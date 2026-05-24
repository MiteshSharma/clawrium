"""`clawctl channel` — Pattern A attachable (NEW noun; stub for bundle 2).

Real implementation lands in bundle 4 (#509). Plan §8 documents the
schema and the Discord/Slack-extraction goal driving the new top-level
noun.
"""

import typer

from clawrium.cli.clawctl._stub import register_stub

__all__ = ["channel_app"]


channel_app = typer.Typer(
    name="channel",
    help="Chat surfaces (Discord, Slack) (Pattern A attachable).",
    no_args_is_help=True,
    add_completion=False,
)

channel_registry_app = typer.Typer(
    name="registry",
    help="CRUD entrypoint for the channel registry.",
    no_args_is_help=True,
    add_completion=False,
)


_GROUP = "channel registry"
_VERBS = (
    ("create", "Register a channel."),
    ("get", "List registered channels."),
    ("describe", "Describe a channel."),
    ("delete", "Delete a channel."),
    ("edit", "Edit a channel."),
)

for _verb, _help in _VERBS:
    register_stub(channel_registry_app, group=_GROUP, verb=_verb, help_text=_help)

channel_app.add_typer(channel_registry_app, name="registry")
