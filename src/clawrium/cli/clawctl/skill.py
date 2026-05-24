"""`clawctl skill` — Pattern A attachable (read-only registry; stub).

Real implementation lands in bundle 4 (#509). Skills are repo-bundled
so the registry is read-only (`get` / `describe`).
"""

import typer

from clawrium.cli.clawctl._stub import register_stub

__all__ = ["skill_app"]


skill_app = typer.Typer(
    name="skill",
    help="Skills catalog (Pattern A attachable, read-only).",
    no_args_is_help=True,
    add_completion=False,
)

skill_registry_app = typer.Typer(
    name="registry",
    help="Read-only entrypoint for the skill registry.",
    no_args_is_help=True,
    add_completion=False,
)


_GROUP = "skill registry"
_VERBS = (
    ("get", "List available skills."),
    ("describe", "Describe a skill."),
)

for _verb, _help in _VERBS:
    register_stub(skill_registry_app, group=_GROUP, verb=_verb, help_text=_help)

skill_app.add_typer(skill_registry_app, name="registry")
