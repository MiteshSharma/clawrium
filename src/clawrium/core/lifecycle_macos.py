"""launchctl-based lifecycle backend for macOS hermes agents.

Counterpart to `core/lifecycle.py:_run_lifecycle_playbook` for Darwin
targets. Where the systemd path runs a per-op playbook
(start.yaml/stop.yaml/restart.yaml) that wraps `systemctl`, the macOS
path just opens a paramiko SSH session and shells out to `launchctl`
in the `system` domain.

Why launchctl and not a playbook: launchctl's bootstrap/bootout/
kickstart trio is the entire surface area we need, and wrapping three
one-line `sudo launchctl ...` calls in three more YAML files would
just add indirection. The plist file itself (rendered in step 6) is
the only artifact that lives on disk.

Functions defined here intentionally mirror the signatures of the
equivalents in `core/lifecycle.py`: when `lifecycle.start_agent()`
sees `os_family == "darwin"` it delegates here. The CLI layer is
unchanged.
"""

from __future__ import annotations

import logging
import shlex
from datetime import datetime, timezone
from typing import Callable, TypedDict

import paramiko

from clawrium.core.launchd import (
    label_for,
    plist_path_for,
    remove_plist,
    render_plist,
    write_plist,
)

logger = logging.getLogger(__name__)


class LifecycleResult(TypedDict, total=False):
    success: bool
    agent: str
    host: str
    operation: str
    pid: int | None
    started_at: str | None
    error: str | None


class LifecycleError(Exception):
    """Raised on terminal failures (missing host record, ssh refused, ...)."""


def _ssh(host: dict) -> paramiko.SSHClient:
    """Open a paramiko SSH session to the host using the per-host key."""
    from clawrium.core.keys import get_host_private_key

    key_id = host.get("key_id") or host["hostname"]
    key_path = get_host_private_key(key_id)
    if not key_path:
        raise LifecycleError(f"No SSH key found for host {host['hostname']!r}")

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host["hostname"],
        port=int(host.get("port", 22)),
        username=host.get("user", "xclm"),
        key_filename=str(key_path),
        timeout=15,
    )
    return client


def _run(client: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def install_service(
    client: paramiko.SSHClient,
    agent_name: str,
    *,
    dashboard_port: int | None = None,
) -> str:
    """Render and write the gateway plist (and dashboard plist if `dashboard_port`)
    for `agent_name`. Returns the gateway plist path.

    Idempotent: re-writing the same content is a no-op. Does NOT bootstrap
    the units — that's start_agent. Always ensures /Users/<agent>/.hermes/logs
    exists so StandardOutPath / StandardErrorPath in the plists resolve.
    """
    contents = render_plist(agent_name)
    path = write_plist(client, agent_name, contents)
    if dashboard_port is not None:
        dash_contents = render_plist(
            agent_name,
            template_name="dashboard.plist.j2",
            dashboard_port=dashboard_port,
        )
        write_plist(client, agent_name, dash_contents, kind="dashboard")
    # Ensure log dir exists with correct ownership; launchd writes there
    # as the agent user.
    _run(
        client,
        "sudo mkdir -p /Users/" + shlex.quote(agent_name) + "/.hermes/logs "
        "&& sudo chown " + shlex.quote(agent_name) + ":staff "
        "/Users/" + shlex.quote(agent_name) + "/.hermes/logs",
    )
    return path


def _bootstrap(
    client: paramiko.SSHClient, agent_name: str, *, kind: str = "gateway"
) -> tuple[int, str, str]:
    """`launchctl bootstrap system <plist>`. Idempotent-ish.

    Bootstrap fails (rc=37 or rc=5) if the unit is already loaded; the
    caller treats that case as success. Other non-zero results bubble up.
    """
    path = plist_path_for(agent_name, kind=kind)
    return _run(client, f"sudo launchctl bootstrap system {shlex.quote(path)}")


def _bootout(
    client: paramiko.SSHClient, agent_name: str, *, kind: str = "gateway"
) -> tuple[int, str, str]:
    """`launchctl bootout system/<label>`. Tolerates "not loaded"."""
    label = label_for(agent_name, kind=kind)
    return _run(client, f"sudo launchctl bootout system/{shlex.quote(label)}")


def _kickstart(
    client: paramiko.SSHClient,
    agent_name: str,
    *,
    kill: bool = False,
    kind: str = "gateway",
) -> tuple[int, str, str]:
    """`launchctl kickstart [-k] system/<label>` — restart in place."""
    label = label_for(agent_name, kind=kind)
    flag = "-k " if kill else ""
    return _run(client, f"sudo launchctl kickstart {flag}system/{shlex.quote(label)}")


def _dashboard_port_from_host(host: dict, agent_name: str) -> int | None:
    """Look up the persisted dashboard port for `agent_name` in `host`.

    install.py persists it under `agents.<name>.config.dashboard.port`.
    Returns None if the agent has no dashboard configured.
    """
    agents = host.get("agents") or {}
    rec = agents.get(agent_name) or {}
    cfg = rec.get("config") or {}
    dash = cfg.get("dashboard") or {}
    port = dash.get("port")
    try:
        return int(port) if port is not None else None
    except (TypeError, ValueError):
        return None


def _bootstrap_with_tolerance(
    client: paramiko.SSHClient, agent_name: str, *, kind: str
) -> tuple[bool, str | None]:
    """`launchctl bootstrap`, treating any "already loaded" signal as success.

    macOS launchctl is annoyingly inconsistent about what it reports when
    a unit is already bootstrapped — observed cases include:
      - rc=5 + "Input/output error" (Sonoma onward)
      - rc=17 + "File exists"
      - rc=37 + "Service already loaded"
      - rc=149 + "Bootstrap failed: 149: Operation already in progress"
    The pragmatic check: any non-zero rc whose output mentions "already",
    "input/output", "file exists", or "service" is treated as success.
    The follow-up kickstart confirms whether the daemon is actually
    running.
    """
    rc, out, err = _bootstrap(client, agent_name, kind=kind)
    if rc == 0:
        return True, None
    combined = (out + err).lower()
    already_loaded = any(
        marker in combined
        for marker in ("already", "input/output", "file exists", "service")
    )
    if already_loaded:
        return True, None
    return False, f"launchctl bootstrap ({kind}) failed (rc={rc}): {err.strip() or out.strip()}"


def start_agent_macos(
    host: dict,
    agent_name: str,
    on_event: Callable[[str, str], None] | None = None,
) -> tuple[bool, str | None]:
    """Bootstrap the gateway (and dashboard, if configured) plists into
    launchd's system domain.

    Returns (success, error). On a fresh install the plists need to be
    rendered + written before bootstrap. On a re-run, bootstrap will
    return "already loaded" — we treat that as success and call
    kickstart to ensure the daemons are actually running.
    """

    def emit(stage: str, message: str) -> None:
        if on_event:
            on_event(stage, message)
        logger.info("[%s] %s", stage, message)

    dashboard_port = _dashboard_port_from_host(host, agent_name)

    client = _ssh(host)
    try:
        emit("start", f"installing plists for {agent_name}")
        install_service(client, agent_name, dashboard_port=dashboard_port)

        emit("start", f"launchctl bootstrap {agent_name} (gateway)")
        ok, err = _bootstrap_with_tolerance(client, agent_name, kind="gateway")
        if not ok:
            return False, err

        emit("start", f"launchctl kickstart {agent_name} (gateway)")
        rc, out, err = _kickstart(client, agent_name, kind="gateway")
        if rc != 0:
            return False, f"launchctl kickstart (gateway) failed (rc={rc}): {err.strip() or out.strip()}"

        if dashboard_port is not None:
            emit("start", f"launchctl bootstrap {agent_name} (dashboard:{dashboard_port})")
            ok, err = _bootstrap_with_tolerance(client, agent_name, kind="dashboard")
            if not ok:
                return False, err
            emit("start", f"launchctl kickstart {agent_name} (dashboard)")
            rc, out, err = _kickstart(client, agent_name, kind="dashboard")
            if rc != 0:
                return False, f"launchctl kickstart (dashboard) failed (rc={rc}): {err.strip() or out.strip()}"

        return True, None
    finally:
        client.close()


def stop_agent_macos(
    host: dict,
    agent_name: str,
    on_event: Callable[[str, str], None] | None = None,
) -> tuple[bool, str | None]:
    """`launchctl bootout` for both dashboard (if present) and gateway.

    Tolerates "could not find service" for both — launchd lacks a systemd
    PartOf= equivalent, so we enumerate the labels explicitly. Dashboard
    is reaped first so the gateway's lifecycle is the last thing the
    operator sees in logs.
    """

    def emit(stage: str, message: str) -> None:
        if on_event:
            on_event(stage, message)
        logger.info("[%s] %s", stage, message)

    client = _ssh(host)
    try:
        for kind in ("dashboard", "gateway"):
            emit("stop", f"launchctl bootout {agent_name} ({kind})")
            rc, out, err = _bootout(client, agent_name, kind=kind)
            combined = (out + err).lower()
            # rc=3 "no such process" + rc=113/varied "could not find service"
            # both signal "wasn't loaded" — idempotent stop tolerates them.
            not_loaded = rc != 0 and (
                "could not find service" in combined
                or "no such process" in combined
                or "no such file" in combined
            )
            if rc != 0 and not not_loaded:
                return False, f"launchctl bootout ({kind}) failed (rc={rc}): {err.strip() or out.strip()}"
        return True, None
    finally:
        client.close()


def restart_agent_macos(
    host: dict,
    agent_name: str,
    on_event: Callable[[str, str], None] | None = None,
) -> tuple[bool, str | None]:
    """`launchctl kickstart -k system/<label>` if loaded, else bootstrap."""

    def emit(stage: str, message: str) -> None:
        if on_event:
            on_event(stage, message)
        logger.info("[%s] %s", stage, message)

    client = _ssh(host)
    try:
        emit("restart", f"launchctl kickstart -k {agent_name}")
        rc, out, err = _kickstart(client, agent_name, kill=True)
        if rc == 0:
            return True, None
        # kickstart fails if not loaded — fall back to fresh bootstrap.
        if "could not find service" in (out + err).lower():
            install_service(client, agent_name)
            rc2, out2, err2 = _bootstrap(client, agent_name)
            if rc2 != 0:
                return False, f"launchctl bootstrap fallback failed: {err2.strip() or out2.strip()}"
            return True, None
        return False, f"launchctl kickstart -k failed (rc={rc}): {err.strip() or out.strip()}"
    finally:
        client.close()


def remove_service_macos(
    host: dict, agent_name: str, on_event: Callable[[str, str], None] | None = None
) -> tuple[bool, str | None]:
    """bootout + delete plist file. Idempotent."""

    def emit(stage: str, message: str) -> None:
        if on_event:
            on_event(stage, message)
        logger.info("[%s] %s", stage, message)

    client = _ssh(host)
    try:
        for kind in ("dashboard", "gateway"):
            emit("remove", f"bootout {agent_name} ({kind})")
            _bootout(client, agent_name, kind=kind)  # tolerate not-loaded
            remove_plist(client, agent_name, kind=kind)
        return True, None
    finally:
        client.close()


__all__ = [
    "LifecycleError",
    "LifecycleResult",
    "install_service",
    "remove_service_macos",
    "restart_agent_macos",
    "start_agent_macos",
    "stop_agent_macos",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
