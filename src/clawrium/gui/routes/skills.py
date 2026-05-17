"""Skills catalog API routes.

Read-only browse of the in-repo skills catalog, mirroring the Phase 1
CLI surface (``clm skill list`` / ``clm skill show``). Backed by
``clawrium.core.skills``; this module never writes to disk and never
mutates agent state. Per-agent install/remove lives under
``/api/agents/{agent}/skills`` and is a later phase.

Status mapping for ``SkillError`` subclasses:

- ``MissingRegistryPrefix``, ``ExternalSourceBlocked``, ``InvalidSkillRef``
  → 422 (request shape is malformed; the user can fix it by retyping)
- ``SkillNotFound`` → 404 (well-formed ref, no such skill in the catalog)
- ``SchemaValidationError`` → 422 (catalog file present but invalid; the
  detail string names the offending field so the catalog author can fix
  it; not surfaced as 500 because catalog files are user-authored)
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from clawrium.core.skills import (
    REGISTRIES,
    ExternalSourceBlocked,
    InvalidSkillRef,
    MissingRegistryPrefix,
    SchemaValidationError,
    SkillError,
    SkillNotFound,
    SkillRef,
    list_skills,
    load_skill,
    parse_skill_ref,
    validate_skill,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _summarize(ref: SkillRef) -> dict[str, Any]:
    """Card-shape summary for the catalog list endpoint.

    Per-skill loader failures degrade to a row with ``description: None``
    rather than blowing up the whole list — same UX rule the CLI uses in
    ``cli/skill.py::_short_description``. A single bad ``_meta.yaml``
    should not blank the GUI catalog tab.
    """
    summary: dict[str, Any] = {
        "ref": str(ref),
        "registry": ref.registry,
        "name": ref.name,
        "description": None,
        "version": None,
    }
    try:
        skill = load_skill(ref)
    except SkillError as error:
        logger.debug("skipping summary for %s: %s", ref, error)
        return summary

    description = skill.metadata.get("description")
    if isinstance(description, str) and description.strip():
        summary["description"] = " ".join(description.split())

    version = skill.metadata.get("version")
    if version is not None:
        summary["version"] = str(version)

    return summary


def _detail(skill_ref: SkillRef) -> dict[str, Any]:
    """Full skill payload for the detail endpoint.

    Exposes the parsed metadata, the SKILL.md body, and a derived
    ``compatibility`` map so the frontend doesn't need to know whether
    the source registry was ``clawrium`` (compatibility lives in
    ``_meta.yaml``) or a native claw (compatibility is implicit: only the
    claw whose registry name matches the ref).
    """
    skill = load_skill(skill_ref)
    # Validate so malformed catalog files surface as 422 (caller maps the
    # exception). Without this, a missing required field in _meta.yaml
    # would return a partial-looking 200 to the GUI.
    validate_skill(skill)

    compatibility = _compatibility_map(skill_ref, skill.metadata)
    return {
        "ref": str(skill.ref),
        "registry": skill.ref.registry,
        "name": skill.ref.name,
        "metadata": skill.metadata,
        "body": skill.body,
        "compatibility": compatibility,
    }


def _compatibility_map(ref: SkillRef, metadata: dict[str, Any]) -> dict[str, bool]:
    """Return a uniform ``{claw: bool}`` shape for the frontend.

    For ``clawrium/*`` we read the ``_meta.yaml.compatibility`` map and
    coerce missing/non-bool entries to ``False`` (same fail-closed rule
    as ``check_agent_compatibility``).

    For ``<claw>/*`` we synthesize ``{<claw>: True, <other>: False}`` so
    the GUI doesn't have to special-case native skills.
    """
    if ref.registry == "clawrium":
        raw = metadata.get("compatibility") or {}
        if not isinstance(raw, dict):
            raw = {}
        return {
            claw: bool(raw.get(claw, False))
            for claw in ("openclaw", "hermes", "zeroclaw")
        }
    return {
        claw: (claw == ref.registry)
        for claw in ("openclaw", "hermes", "zeroclaw")
    }


def _map_error(error: SkillError) -> HTTPException:
    """Translate a ``SkillError`` into an HTTP exception with stable codes."""
    if isinstance(error, SkillNotFound):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(
        error,
        (MissingRegistryPrefix, ExternalSourceBlocked, InvalidSkillRef),
    ):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, SchemaValidationError):
        return HTTPException(status_code=422, detail=str(error))
    # Defensive: a future SkillError subclass should not become a 500.
    return HTTPException(status_code=500, detail=str(error))


@router.get("")
async def list_skills_route() -> dict[str, Any]:
    """Catalog listing, grouped by registry.

    Response shape:

    ```
    {
      "registries": ["clawrium", "openclaw", "hermes", "zeroclaw"],
      "skills": {
        "clawrium": [<summary>, ...],
        "openclaw": [<summary>, ...],
        ...
      }
    }
    ```

    Empty registries appear as empty lists, not omitted keys — the GUI
    renders a tab per registry regardless. The ``registries`` echo lets
    the frontend hold tab order without re-importing the constant.
    """

    def _build() -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {
            registry: [] for registry in REGISTRIES
        }
        try:
            refs = list_skills()
        except SkillError as error:
            # No catalog at all is a 500 only if it's unexpected; the
            # underlying error class is SkillNotFound on missing dir,
            # which we surface as an empty catalog rather than a hard
            # error so the GUI still renders the empty-state tab.
            logger.warning("skills catalog unavailable: %s", error)
            return {"registries": list(REGISTRIES), "skills": grouped}
        for ref in refs:
            grouped[ref.registry].append(_summarize(ref))
        return {"registries": list(REGISTRIES), "skills": grouped}

    return await asyncio.to_thread(_build)


@router.get("/{registry}/{name}")
async def get_skill_route(registry: str, name: str) -> dict[str, Any]:
    """Detail view for a single ``<registry>/<name>`` skill."""
    raw_ref = f"{registry}/{name}"

    def _resolve() -> dict[str, Any]:
        try:
            ref = parse_skill_ref(raw_ref)
            return _detail(ref)
        except SkillError as error:
            raise _map_error(error) from error

    try:
        return await asyncio.to_thread(_resolve)
    except HTTPException:
        raise
