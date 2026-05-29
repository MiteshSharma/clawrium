"""`clawctl host create <hostname>` — register a host record.

On first run for a given hostname:
  1. Generate a per-host ed25519 keypair (if one does not already exist).
  2. Verify SSH access as `xclm` using that key.
  3. On failure: print the manual setup commands (Linux + macOS, pubkey
     inlined) and exit non-zero so the user can run them on the host
     and re-invoke this command.
  4. On success: persist the host record to `hosts.json`.

Re-running after manual setup is idempotent — the keypair is reused,
the SSH check succeeds, and the record write is a no-op when the
existing record already matches.

Auto-bootstrap (`--bootstrap`) was removed in #547. The previous
implementation assumed passwordless sudo as the bootstrap user, but
the paramiko exec channel has no PTY/askpass, so every `sudo` step
silently failed on hosts that actually needed bootstrapping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.markup import escape as rich_escape

from clawrium.cli.clawctl._common import (
    require_flag,
    validate_alias,
    validate_hostname,
)
from clawrium.cli.output import emit_error, stream_action
from clawrium.core.hosts import (
    DuplicateHostError,
    HostsFileCorruptedError,
    add_host,
    get_host,
)
from clawrium.core.keys import (
    generate_host_keypair,
    get_host_private_key,
    read_public_key,
)
from clawrium.core.ssh_connection import (
    HostKeyVerificationRequired,
    test_ssh_connection,
)

console = Console()


def create(
    hostname: str = typer.Argument(..., help="Hostname or IP of the new host."),
    user: Optional[str] = typer.Option(
        None,
        "--user",
        "-u",
        help="Management user on the host (must be 'xclm').",
    ),
    port: int = typer.Option(22, "--port", "-p", min=1, max=65535, help="SSH port."),
    alias: Optional[str] = typer.Option(
        None, "--alias", "-a", help="Display alias for the host."
    ),
) -> None:
    """Create a host record after verifying SSH access to the management user."""
    validate_hostname(hostname)
    if alias is not None:
        validate_alias(alias)
    require_flag(user, flag="--user")
    if user != "xclm":
        emit_error(
            f"--user must be 'xclm' (got {user!r})",
            hint=(
                "clawrium manages hosts as the dedicated 'xclm' user; "
                "see docs/host-preparation.md to create it"
            ),
        )

    try:
        existing = get_host(hostname) or (get_host(alias) if alias else None)
    except HostsFileCorruptedError as exc:
        emit_error(str(exc), hint="check ~/.config/clawrium/hosts.json")

    if existing:
        if existing.get("hostname") == hostname and existing.get("user") == user:
            stream_action(
                resource=f"host/{alias or hostname}",
                message=f"already exists on {hostname}",
            )
            return
        emit_error(
            f"host {hostname!r} already registered with different settings",
            hint="clawctl host edit to modify, or clawctl host delete first",
        )

    private_key = _ensure_host_keypair(hostname)
    if not _verify_xclm_access(hostname, port, private_key):
        _print_manual_setup(hostname)
        raise typer.Exit(code=1)

    now = datetime.now(timezone.utc).isoformat()
    record: dict = {
        "hostname": hostname,
        "key_id": hostname,
        "port": port,
        "user": user,
        "auth_method": "key",
        "hardware": {},
        "metadata": {"added_at": now, "last_seen": None, "labels": {}},
        "addresses": [
            {
                "address": hostname,
                "is_primary": True,
                "label": None,
                "added_at": now,
            }
        ],
        "agents": {},
    }
    if alias:
        record["alias"] = alias

    try:
        add_host(record)
    except DuplicateHostError as exc:
        emit_error(str(exc), hint="clawctl host delete to remove first")
    except HostsFileCorruptedError as exc:
        emit_error(str(exc), hint="check ~/.config/clawrium/hosts.json")

    display = alias or hostname
    stream_action(resource=f"host/{display}", message=f"created on {hostname}:{port}")


def _ensure_host_keypair(hostname: str) -> str:
    """Return the path to the host's private key, generating it if missing."""
    existing = get_host_private_key(hostname)
    if existing:
        return str(existing)
    console.print(
        f"Generating SSH keypair for [cyan]{rich_escape(hostname)}[/cyan]..."
    )
    private_key_path, public_key_path = generate_host_keypair(hostname)
    console.print(f"[green]Keypair created:[/green] {rich_escape(str(public_key_path))}")
    return str(private_key_path)


def _verify_xclm_access(hostname: str, port: int, private_key: str) -> bool:
    """True when SSH as xclm using the per-host key succeeds."""
    try:
        success, message = test_ssh_connection(
            hostname=hostname, port=port, user="xclm", key_filename=private_key
        )
    except HostKeyVerificationRequired as exc:
        console.print(
            f"[yellow]Host key prompt required for "
            f"{rich_escape(exc.hostname)}[/yellow] "
            f"(fingerprint {rich_escape(exc.fingerprint)})."
        )
        console.print(
            "Run [cyan]ssh -p "
            f"{port} xclm@{rich_escape(hostname)}[/cyan] once to record the host key, "
            "then re-run this command."
        )
        return False
    if not success:
        console.print(
            f"[yellow]xclm SSH verification failed:[/yellow] {rich_escape(message)}"
        )
    return success


def _print_manual_setup(hostname: str) -> None:
    """Print Linux + macOS manual setup blocks with the public key inlined."""
    pubkey = read_public_key(hostname) or ""
    safe_pubkey = pubkey.strip().replace('"', '\\"')

    console.print(
        "\n[bold]Manual setup required.[/bold] "
        "Log into the host with a sudo-capable user and run the block that "
        "matches its OS:\n"
    )

    console.print("[bold cyan]## Linux[/bold cyan]")
    console.print("[dim]# Create xclm user[/dim]")
    console.print("sudo useradd -m -s /bin/bash xclm")
    console.print("[dim]# Passwordless sudo[/dim]")
    console.print(
        'echo "xclm ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/xclm'
    )
    console.print("sudo chmod 440 /etc/sudoers.d/xclm")
    console.print("[dim]# Authorized key[/dim]")
    console.print("sudo mkdir -p /home/xclm/.ssh && sudo chmod 700 /home/xclm/.ssh")
    console.print(
        f'echo "{rich_escape(safe_pubkey)}" | sudo tee /home/xclm/.ssh/authorized_keys',
        soft_wrap=False,
    )
    console.print("sudo chmod 600 /home/xclm/.ssh/authorized_keys")
    console.print("sudo chown -R xclm:xclm /home/xclm/.ssh\n")

    console.print("[bold cyan]## macOS[/bold cyan]")
    console.print("[dim]# Create xclm user via dscl[/dim]")
    console.print("sudo dscl . -create /Users/xclm")
    console.print("sudo dscl . -create /Users/xclm UserShell /bin/bash")
    console.print('sudo dscl . -create /Users/xclm RealName "Clawrium Mgmt"')
    console.print("sudo dscl . -create /Users/xclm UniqueID 600")
    console.print("sudo dscl . -create /Users/xclm PrimaryGroupID 20")
    console.print("sudo dscl . -create /Users/xclm NFSHomeDirectory /Users/xclm")
    console.print("sudo mkdir -p /Users/xclm && sudo chown xclm:staff /Users/xclm")
    console.print("[dim]# Passwordless sudo[/dim]")
    console.print(
        'echo "xclm ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/xclm'
    )
    console.print("sudo chmod 440 /etc/sudoers.d/xclm")
    console.print("[dim]# Authorized key[/dim]")
    console.print(
        "sudo mkdir -p /Users/xclm/.ssh && sudo chmod 700 /Users/xclm/.ssh"
    )
    console.print(
        f'echo "{rich_escape(safe_pubkey)}" | sudo tee /Users/xclm/.ssh/authorized_keys',
        soft_wrap=False,
    )
    console.print("sudo chmod 600 /Users/xclm/.ssh/authorized_keys")
    console.print("sudo chown -R xclm:staff /Users/xclm/.ssh")
    console.print(
        "[dim]# Critical Mac-only step: SSH ACL group "
        "(without this, sshd silently rejects xclm)[/dim]"
    )
    console.print(
        "sudo dseditgroup -o edit -a xclm -t user com.apple.access_ssh\n"
    )

    console.print(
        f"Then re-run: [cyan]clawctl host create {rich_escape(hostname)} "
        "--user xclm[/cyan]"
    )
