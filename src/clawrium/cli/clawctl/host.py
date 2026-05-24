"""`clawctl host` — Pattern B target (stub surface for bundle 2).

Real implementation lands in bundle 3 (#508). This bundle only
registers the verb surface so `clawctl host --help` lists the planned
commands from plan §4 and each one prints the placeholder line.
"""

import typer

from clawrium.cli.clawctl._stub import register_stub

__all__ = ["host_app"]


host_app = typer.Typer(
    name="host",
    help="Manage fleet machines (hosts).",
    no_args_is_help=True,
    add_completion=False,
)


_GROUP = "host"
_VERBS = (
    ("create", "Create a host record."),
    ("get", "List hosts."),
    ("describe", "Describe a host."),
    ("delete", "Delete a host record."),
    ("edit", "Edit a host record."),
    ("reset", "Wipe remote state on a host."),
    ("alias", "Manage host aliases (multi-value)."),
    ("address", "Manage host addresses."),
    ("label", "Manage host labels."),
    ("registry", "Read-only host-types catalog."),
)

for _verb, _help in _VERBS:
    register_stub(host_app, group=_GROUP, verb=_verb, help_text=_help)
