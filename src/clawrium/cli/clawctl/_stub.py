"""Shared helpers for the `clawctl` stub group commands.

The wording `Not implemented: <group> <verb>` is the single contract
asserted in tests (see plan §"Specific Outcomes to Validate"). Keeping
it in one place means bundles 3/4 can replace stubs verb-by-verb
without drifting the message.
"""

import typer

__all__ = ["echo_not_implemented", "register_stub"]


def echo_not_implemented(group: str, verb: str) -> None:
    """Print the canonical placeholder line. Exit 0."""
    typer.echo(f"Not implemented: {group} {verb}")


def register_stub(
    app: typer.Typer,
    *,
    group: str,
    verb: str,
    help_text: str = "",
) -> None:
    """Register a `<verb>` command on `app` that emits the placeholder.

    Used by the per-group stub modules so the surface visible in
    `clawctl <group> --help` matches the planned §4 verb list, even
    before bundles 3-4 wire up the real logic.
    """

    def _stub() -> None:
        echo_not_implemented(group, verb)

    _stub.__doc__ = help_text or f"{verb} (not yet implemented)"
    app.command(name=verb)(_stub)
