"""Provider-attachment data model for agents.

Centralizes the shape of `agent.providers` across agent types. For
hermes (issue #501), an attachment is a dict `{name, role, model}`
where `role` is `primary` or one of nine upstream auxiliary slots.
For zeroclaw and openclaw, attachments stay as bare provider-name
strings (singleton invariant preserved).

Storage may carry either the legacy list-of-strings shape or the new
list-of-objects shape; `normalize()` returns the canonical form for
the agent type. Validation enforces the per-agent invariants. Callers
should normalize before reading and validate before writing.
"""

from __future__ import annotations

from typing import Iterable

__all__ = [
    "HERMES_AGENT_TYPE",
    "PRIMARY_ROLE",
    "AUXILIARY_SLOTS",
    "VALID_ROLES",
    "AttachmentError",
    "supports_multi_provider",
    "normalize",
    "validate",
    "get_primary",
    "get_auxiliary",
]


HERMES_AGENT_TYPE = "hermes"
PRIMARY_ROLE = "primary"

# Upstream auxiliary slots from NousResearch/hermes-agent
# hermes_cli/config.py:716-794 (v2026.5.7). Order is not significant
# at the data layer but kept deterministic for predictable rendering.
AUXILIARY_SLOTS: tuple[str, ...] = (
    "vision",
    "web_extract",
    "compression",
    "session_search",
    "skills_hub",
    "approval",
    "mcp",
    "title_generation",
    "curator",
)

VALID_ROLES: frozenset[str] = frozenset((PRIMARY_ROLE, *AUXILIARY_SLOTS))


class AttachmentError(ValueError):
    """Raised when provider attachments violate per-agent invariants."""


def supports_multi_provider(agent_type: str | None) -> bool:
    """Return True iff the agent type allows multiple provider attachments."""
    return agent_type == HERMES_AGENT_TYPE


def normalize(
    raw: object, agent_type: str | None
) -> list[dict] | list[str]:
    """Return the canonical attachment list for an agent type.

    For hermes: returns list of `{name, role, model}` dicts. Legacy
    list-of-strings input is migrated forward (first string becomes
    `role=primary`, additional strings get no role and will fail
    validation — but that branch only fires on hand-edited records;
    the live `attach` surface enforces singleton today).

    For other agent types: returns list of provider-name strings.
    Object-shape entries are reduced back to their `name` field so
    a downgrade direction stays representable for non-hermes paths.

    Non-list / falsy input returns an empty list.
    """
    if not isinstance(raw, list):
        return []

    if supports_multi_provider(agent_type):
        out: list[dict] = []
        primary_assigned = False
        for entry in raw:
            if isinstance(entry, str):
                role = PRIMARY_ROLE if not primary_assigned else ""
                if role == PRIMARY_ROLE:
                    primary_assigned = True
                out.append({"name": entry, "role": role, "model": ""})
            elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
                role = entry.get("role", "")
                if not isinstance(role, str):
                    role = ""
                if role == PRIMARY_ROLE:
                    primary_assigned = True
                model = entry.get("model", "")
                if not isinstance(model, str):
                    model = ""
                out.append({"name": entry["name"], "role": role, "model": model})
        return out

    # Singleton / list-of-strings agent types.
    out_str: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            out_str.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
            out_str.append(entry["name"])
    return out_str


def validate(attachments: Iterable[object], agent_type: str | None) -> None:
    """Enforce per-agent invariants on a normalized attachment list.

    For hermes:
      - every entry has a non-empty `name`
      - every entry's `role` is in VALID_ROLES (empty role rejected)
      - exactly one entry has `role == primary` (when the list is non-empty)
      - auxiliary roles are unique across the list

    For other agent types:
      - at most one attachment (existing singleton invariant)
    """
    items = list(attachments)

    if not supports_multi_provider(agent_type):
        if len(items) > 1:
            # Phrase "single-provider invariant" pinned for back-compat:
            # the openclaw/zeroclaw error message used to be raised
            # directly from lifecycle.py with this exact phrase, and
            # tests + docs reference it.
            raise AttachmentError(
                f"agent type '{agent_type}' has {len(items)} providers attached; "
                f"single-provider invariant requires exactly one"
            )
        return

    if not items:
        return

    primary_count = 0
    seen_aux: set[str] = set()
    for entry in items:
        if not isinstance(entry, dict):
            raise AttachmentError(
                f"hermes provider attachment must be an object, got {type(entry).__name__}"
            )
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise AttachmentError("hermes provider attachment requires non-empty 'name'")
        role = entry.get("role")
        if role not in VALID_ROLES:
            raise AttachmentError(
                f"hermes provider attachment {name!r} has invalid role {role!r}; "
                f"expected one of {sorted(VALID_ROLES)}"
            )
        if role == PRIMARY_ROLE:
            primary_count += 1
        else:
            if role in seen_aux:
                raise AttachmentError(
                    f"hermes auxiliary slot {role!r} already filled; "
                    f"each slot accepts one provider"
                )
            seen_aux.add(role)

    if primary_count != 1:
        raise AttachmentError(
            f"hermes requires exactly one primary provider, found {primary_count}"
        )


def get_primary(attachments: Iterable[object]) -> dict | None:
    """Return the primary attachment dict for hermes, or None.

    Accepts a normalized hermes attachment list (list of dicts). For
    other shapes (list of strings) returns None — non-hermes agents
    have no notion of "primary" beyond the singleton itself.
    """
    for entry in attachments:
        if isinstance(entry, dict) and entry.get("role") == PRIMARY_ROLE:
            return entry
    return None


def get_auxiliary(attachments: Iterable[object]) -> list[dict]:
    """Return all non-primary hermes attachments in input order."""
    out: list[dict] = []
    for entry in attachments:
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("role"), str)
            and entry.get("role")
            and entry["role"] != PRIMARY_ROLE
        ):
            out.append(entry)
    return out
