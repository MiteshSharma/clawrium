"""Shared agent helpers: lookup + row serialization.

Centralizes the `(hostname, host_record, agent_key, claw_record)`
discovery tuple so every verb that takes an `<agent-name>` argument
resolves it the same way (via `core/hosts.py:get_agent_by_name`).
"""

from __future__ import annotations

from typing import Optional

from clawrium.cli.clawctl._common import now_seconds_since
from clawrium.cli.clawctl.host._shared import primary_address
from clawrium.cli.output import emit_error
from clawrium.core.hosts import HostsFileCorruptedError, get_agent_by_name


def safe_resolve_agent(agent_name: str) -> tuple[dict, str, dict]:
    """Resolve `agent_name` → (host_record, agent_key, claw_record).

    Wraps `core/hosts.py:get_agent_by_name` with a clean error path
    for the not-found case (plan §6.12 sample).
    """
    try:
        result = get_agent_by_name(agent_name)
    except HostsFileCorruptedError as exc:
        emit_error(str(exc), hint="check ~/.config/clawrium/hosts.json")
    if not result:
        emit_error(
            f"agent {agent_name!r} not found",
            hint="clawctl agent get",
        )
    host, agent_key, claw_record = result  # type: ignore[misc]
    return host, agent_key, claw_record


def agent_status(claw_record: dict) -> str:
    """Derive a plan-§6.13 status token from a claw_record.

    The legacy record stores `status` (install-time) and runtime status
    is computed elsewhere (`core/health.py`). For #508 we surface
    install-time status, mapped onto the plan vocabulary:
    - installed + onboarding ready → `ready`
    - installed + onboarding incomplete → `onboarding`
    - failed → `failed`
    - pending → `pending`
    - everything else → `unknown`

    Bundle 5 (#510) wires runtime health checks in.
    """
    install_status = (claw_record.get("status") or "").lower()
    if install_status == "failed":
        return "failed"
    if install_status == "pending":
        return "pending"
    if install_status == "installed":
        state = claw_record.get("onboarding", {}).get("state", "pending").lower()
        if state == "ready":
            return "ready"
        return "onboarding"
    return "unknown"


def agent_to_row(
    host: dict,
    agent_key: str,
    claw_record: dict,
) -> dict:
    """Render an agent as a serializable row (plan §6.5 schema)."""
    install_at = claw_record.get("installed_at")
    return {
        "kind": "agent",
        "name": claw_record.get("agent_name") or agent_key,
        "type": claw_record.get("type") or agent_key,
        "host": host.get("alias") or host.get("hostname", ""),
        "address": primary_address(host),
        "provider": _first_provider(claw_record),
        "status": agent_status(claw_record),
        "age_seconds": now_seconds_since(install_at),
        "port": claw_record.get("gateway", {}).get("port"),
        "version": claw_record.get("version", ""),
        "installed_at": install_at,
    }


def _first_provider(claw_record: dict) -> Optional[str]:
    """Best-effort: surface the first configured provider name."""
    config = claw_record.get("config", {}) or {}
    providers = config.get("providers") or {}
    if isinstance(providers, dict) and providers:
        return next(iter(providers.keys()))
    if isinstance(providers, list) and providers:
        first = providers[0]
        if isinstance(first, dict):
            return first.get("name")
        return str(first)
    return None
