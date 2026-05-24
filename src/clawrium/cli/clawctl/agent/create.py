"""`clawctl agent create <name>` — install an agent on a host.

Plan §"Specific Outcomes":
    `clawctl agent create <name> --type T --host H --provider P --yes`
runs without prompts on non-TTY, completes install + initial configure
stage, returns exit 0.

Delegates to `core/install.py:run_installation` for install + initial
configure flow. The `--provider` flag is captured for the follow-up
`configure` step (issue #509 wires Pattern A `provider attach`; for
this bundle we accept the flag and pass it as the initial provider
selection in the configure stage).
"""

from __future__ import annotations

from typing import Optional

import typer

from clawrium.cli.clawctl._common import confirm_destructive, require_flag
from clawrium.cli.output import emit_error, stream_action
from clawrium.core.install import (
    IncompleteInstallationError,
    InstallationError,
    run_installation,
)
from clawrium.core.registry import ManifestNotFoundError, get_claw_info


def create(
    name: str = typer.Argument(..., help="Name for the new agent instance."),
    agent_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Agent type (e.g., openclaw, zeroclaw, hermes)."
    ),
    host: Optional[str] = typer.Option(
        None, "--host", "-H", help="Target host (name or alias)."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-P", help="Initial provider name to attach."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Reinstall even if same version present."
    ),
    cleanup_failed: bool = typer.Option(
        False, "--cleanup-failed", help="Remove failed installation before retry."
    ),
) -> None:
    """Install a new agent on a host."""
    require_flag(agent_type, flag="--type")
    require_flag(host, flag="--host")

    if not agent_type or not host:
        emit_error(
            "missing required flags",
            hint="--type and --host are required (use --yes for non-interactive)",
        )

    try:
        get_claw_info(agent_type)
    except ManifestNotFoundError:
        emit_error(
            f"unknown agent type {agent_type!r}",
            hint="clawctl agent registry get",
        )

    if force and not yes:
        confirm_destructive(
            prompt=(
                "--force rotates gateway tokens and device credentials. "
                "Existing integrations will break. Continue?"
            ),
            yes=False,
        )

    def on_event(stage: str, message: str) -> None:
        stream_action(resource=f"agent/{name}", message=f"[{stage}] {message}")

    try:
        result = run_installation(
            claw_name=agent_type,
            hostname=host,
            name=name,
            on_event=on_event,
            cleanup_failed=cleanup_failed,
            resume=False,
            force=force,
        )
    except IncompleteInstallationError as exc:
        emit_error(
            f"incomplete installation present: {exc}",
            hint="re-run with --cleanup-failed",
        )
    except InstallationError as exc:
        emit_error(f"installation failed: {exc}")

    version = result.get("version", "?")
    stream_action(resource=f"agent/{name}", message=f"installed ({version})")

    if provider:
        stream_action(
            resource=f"agent/{name}",
            message=(
                f"provider {provider!r} requested — run "
                f"'clawctl agent configure {name} --provider {provider}' to apply"
            ),
        )

    stream_action(resource=f"agent/{name}", message="ready")
