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


def resolve_agent_key(host: dict, agent_name: str) -> str:
    """Return the dict key under `host.agents` that matches `agent_name`.

    `safe_resolve_agent` returns the agent's *type* string from
    `core/hosts.py:get_agent_by_name`, which is not necessarily the
    dict key used to mutate the agent record (modern installs key by
    name, legacy installs key by type). This helper re-scans the
    host's agents map to find the canonical key.

    ATX iter-2 W3: extracted from three identical copies (`agent/
    provider.py`, `agent/channel.py`, `agent/integration.py`) so any
    future change to the resolution rule only has to land here.
    """
    agents = host.get("agents", {}) or {}
    for key, record in agents.items():
        if not isinstance(record, dict):
            continue
        if agent_name in (key, record.get("agent_name"), record.get("name")):
            return key
    emit_error(
        f"agent {agent_name!r} not found on host {host.get('hostname', '?')}",
        hint="clawctl agent get",
    )


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
    """Surface the first attached provider name for the describe/get row.

    Read order (falsy/malformed at any tier falls through to the next):
    1. `claw_record["providers"]` — the new attach list (Pattern A; #426/#509).
       Single-provider invariant is enforced at attach time, so index 0 is
       the canonical name. Accepts both `["name"]` (string entries) and
       `[{"name": "..."}]` (dict entries) shapes.
    2. `claw_record["config"]["provider"]["name"]` — the materialization
       layer written by `sync_agent` (lifecycle.py:945-992) on every
       successful sync/configure with a provider attached. Absent on
       fresh `clawctl agent create` records (config={}) and on agents
       whose last configure call failed.
    3. `claw_record["config"]["providers"]` — vestigial plural-key path
       kept for any handwritten or third-party record that uses it.
       Accepts dict (`{name: {...}}`) and list (`[name, ...]` /
       `[{"name": "..."}, ...]`) shapes. Terminal tier — anything
       malformed here returns None (no further fallback).

    String entries are validated against `PROVIDER_NAME_PATTERN` (the
    same pattern enforced at write time by `validate_provider_name`).
    Mismatches fall through rather than render — this closes the
    write-time/read-time validation asymmetry against handwritten
    records that contain markup or other non-conforming characters.
    """
    from clawrium.core.providers.storage import PROVIDER_NAME_PATTERN

    def _accept(value: object) -> Optional[str]:
        """Return value if it's a non-empty, pattern-matching string."""
        if isinstance(value, str) and value and PROVIDER_NAME_PATTERN.match(value):
            return value
        return None

    attached = claw_record.get("providers")
    if isinstance(attached, list) and attached:
        first = attached[0]
        accepted = _accept(first)
        if accepted:
            return accepted
        if isinstance(first, dict):
            accepted = _accept(first.get("name"))
            if accepted:
                return accepted

    config = claw_record.get("config", {}) or {}
    materialized = config.get("provider")
    if isinstance(materialized, dict):
        accepted = _accept(materialized.get("name"))
        if accepted:
            return accepted

    providers = config.get("providers") or {}
    if isinstance(providers, dict) and providers:
        # Dict key path: validate the key the same way as other tiers
        # so e.g. `{"[bold]x[/]": {...}}` doesn't render markup.
        accepted = _accept(next(iter(providers.keys())))
        if accepted:
            return accepted
    elif isinstance(providers, list) and providers:
        first = providers[0]
        accepted = _accept(first)
        if accepted:
            return accepted
        if isinstance(first, dict):
            accepted = _accept(first.get("name"))
            if accepted:
                return accepted
    return None
