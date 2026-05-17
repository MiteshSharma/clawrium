"""Tests for the skills GUI routes.

Covers the 200/404/422 paths called out in issue #383's exit gates:

- ``GET /api/skills`` returns a registry-grouped catalog (200) and
  includes empty registries as empty lists, not omitted keys.
- ``GET /api/skills/{registry}/{name}`` resolves real skills (200) and
  maps ``SkillError`` subclasses to the right HTTP status:
  malformed ref / unknown registry → 422; missing skill → 404; bogus
  ``_meta.yaml`` content → 422 (catalog-author error, not a 5xx).

The route delegates loading to ``clawrium.core.skills`` against the
in-repo catalog. We use the real catalog for happy paths and a tmp
catalog (monkey-patched into ``core.skills``) for the schema-error path
so we don't have to corrupt the shipping ``skills/clawrium/tdd``.
"""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from clawrium.core import skills as core_skills
from clawrium.gui.routes import skills as skills_route


def _run(coro):
    return asyncio.run(coro)


# ---------- GET /api/skills ----------------------------------------------------


def test_list_returns_all_registries_grouped():
    result = _run(skills_route.list_skills_route())

    assert result["registries"] == list(core_skills.REGISTRIES)
    assert set(result["skills"].keys()) == set(core_skills.REGISTRIES)
    for registry in core_skills.REGISTRIES:
        assert isinstance(result["skills"][registry], list)


def test_list_includes_clawrium_tdd_summary():
    result = _run(skills_route.list_skills_route())

    clawrium_entries = result["skills"]["clawrium"]
    refs = {entry["ref"] for entry in clawrium_entries}
    assert "clawrium/tdd" in refs

    tdd = next(e for e in clawrium_entries if e["ref"] == "clawrium/tdd")
    assert tdd["registry"] == "clawrium"
    assert tdd["name"] == "tdd"
    assert isinstance(tdd["description"], str) and tdd["description"]
    # Version is optional in the schema but locked in Phase 0 for the
    # seed skill — confirms the loader didn't silently drop it.
    assert tdd["version"]


def test_list_does_not_leak_skill_md_body():
    result = _run(skills_route.list_skills_route())
    blob = json.dumps(result)
    # The summary endpoint must stay light — SKILL.md bodies are only
    # served by the detail endpoint. Catch this if the summary shape
    # accidentally absorbs the body field later.
    assert "Red → Green → Refactor" not in blob
    # Explicit field-shape guard: no per-summary entry should carry a
    # `body` or `metadata` key. Previously this assertion was a vacuous
    # OR — the literal `"skill.md"` never appears in JSON keys so the
    # short-circuit made the test pass regardless of leaks.
    for registry_entries in result["skills"].values():
        for entry in registry_entries:
            assert "body" not in entry, entry
            assert "metadata" not in entry, entry
            assert set(entry.keys()) <= {
                "ref",
                "registry",
                "name",
                "description",
                "version",
            }, entry


def test_list_returns_empty_catalog_when_missing(monkeypatch, tmp_path):
    """A bare tmp dir is not a valid catalog; the route should degrade
    to empty lists per registry rather than 500."""
    empty_root = tmp_path / "no-catalog"
    empty_root.mkdir()
    monkeypatch.setattr(core_skills, "_catalog_root", lambda: empty_root)

    result = _run(skills_route.list_skills_route())
    assert result["registries"] == list(core_skills.REGISTRIES)
    for registry in core_skills.REGISTRIES:
        assert result["skills"][registry] == []


# ---------- GET /api/skills/{registry}/{name} ---------------------------------


def test_detail_returns_metadata_and_body_for_clawrium_tdd():
    result = _run(skills_route.get_skill_route("clawrium", "tdd"))

    assert result["ref"] == "clawrium/tdd"
    assert result["registry"] == "clawrium"
    assert result["name"] == "tdd"
    assert result["metadata"]["name"] == "tdd"
    assert isinstance(result["body"], str)
    assert result["body"].strip(), "SKILL.md body should be non-empty"
    # Compatibility map is normalized — every native claw key present.
    assert set(result["compatibility"].keys()) == {
        "openclaw",
        "hermes",
        "zeroclaw",
    }
    # clawrium/tdd is meant to run on every native claw.
    assert result["compatibility"]["openclaw"] is True
    assert result["compatibility"]["hermes"] is True
    assert result["compatibility"]["zeroclaw"] is True


def test_detail_metadata_is_whitelisted():
    """The detail endpoint must only ship presentation-layer fields —
    no `native.*` blocks, no `compatibility` mirror, no future
    free-form `_meta.yaml` additions."""
    result = _run(skills_route.get_skill_route("clawrium", "tdd"))
    metadata_keys = set(result["metadata"].keys())
    assert metadata_keys <= {
        "name",
        "description",
        "version",
        "license",
        "author",
        "platforms",
    }, metadata_keys
    # Specifically: `native` and `compatibility` are present in the
    # source _meta.yaml but must not leak to the wire.
    assert "native" not in result["metadata"]
    assert "compatibility" not in result["metadata"]


def test_detail_unknown_registry_returns_422():
    with pytest.raises(HTTPException) as exc:
        _run(skills_route.get_skill_route("bogus", "tdd"))
    assert exc.value.status_code == 422
    assert "bogus" in str(exc.value.detail)


def test_detail_invalid_name_returns_422():
    with pytest.raises(HTTPException) as exc:
        _run(skills_route.get_skill_route("clawrium", "Bad Name"))
    assert exc.value.status_code == 422


def test_detail_missing_skill_returns_404():
    with pytest.raises(HTTPException) as exc:
        _run(skills_route.get_skill_route("clawrium", "does-not-exist"))
    assert exc.value.status_code == 404


def test_detail_native_skill_compatibility_self_only(monkeypatch, tmp_path):
    """A native ``<claw>/<name>`` skill must report compatibility only
    with its own claw — the GUI relies on this to disable install on
    other agent types."""
    catalog = _build_native_catalog(tmp_path)
    monkeypatch.setattr(core_skills, "_catalog_root", lambda: catalog)
    # Schema cache is module-level; clear so the tmp _schema/ files are
    # used in the validate path.
    core_skills._SCHEMA_CACHE.clear()

    result = _run(skills_route.get_skill_route("hermes", "nativetest"))
    assert result["compatibility"] == {
        "openclaw": False,
        "hermes": True,
        "zeroclaw": False,
    }


def test_detail_schema_error_returns_422(monkeypatch, tmp_path):
    """A clawrium skill whose ``_meta.yaml.name`` disagrees with its
    directory name fails ``validate_skill`` — the route should surface
    this as 422 (catalog-author error), not 500."""
    catalog = _build_catalog_with_bad_clawrium_meta(tmp_path)
    monkeypatch.setattr(core_skills, "_catalog_root", lambda: catalog)
    core_skills._SCHEMA_CACHE.clear()

    with pytest.raises(HTTPException) as exc:
        _run(skills_route.get_skill_route("clawrium", "badmeta"))
    assert exc.value.status_code == 422
    # The 422 body must not contain absolute filesystem paths — those
    # are logged server-side, not echoed to the client.
    detail = str(exc.value.detail)
    assert str(tmp_path) not in detail
    assert "/_meta.yaml" not in detail
    assert "/SKILL.md" not in detail
    # And it must still identify which skill failed — generic enough
    # not to leak paths, specific enough to be actionable.
    assert "clawrium/badmeta" in detail


# ---------- Helpers ------------------------------------------------------------


def _copy_schemas(target_root: Path) -> None:
    """Copy the real schema files into a tmp catalog so validation has
    something to load. The schemas don't change between tests."""
    src_schema = core_skills._catalog_root.__wrapped__() if hasattr(
        core_skills._catalog_root, "__wrapped__"
    ) else None
    # Source schemas live next to the repo's real catalog. Use the
    # repo-root fallback path directly to keep this helper independent
    # of any monkeypatching that may already be in effect.
    repo_schema = Path(__file__).resolve().parents[1] / "skills" / "_schema"
    assert repo_schema.is_dir(), f"expected schema dir at {repo_schema}"
    dst_schema = target_root / "_schema"
    dst_schema.mkdir(parents=True, exist_ok=True)
    (dst_schema / "clawrium.schema.json").write_text(
        (repo_schema / "clawrium.schema.json").read_text()
    )
    native_src = repo_schema / "native"
    native_dst = dst_schema / "native"
    native_dst.mkdir(parents=True, exist_ok=True)
    for child in native_src.iterdir():
        (native_dst / child.name).write_text(child.read_text())
    del src_schema  # quiet ruff


def _build_native_catalog(tmp_path: Path) -> Path:
    root = tmp_path / "catalog"
    root.mkdir()
    _copy_schemas(root)
    skill_dir = root / "hermes" / "nativetest"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\n"
        "name: nativetest\n"
        "description: A native hermes skill used in tests.\n"
        "version: 0.1.0\n"
        "---\n"
        "# Body\n"
    )
    return root


def _build_catalog_with_bad_clawrium_meta(tmp_path: Path) -> Path:
    root = tmp_path / "catalog"
    root.mkdir()
    _copy_schemas(root)
    skill_dir = root / "clawrium" / "badmeta"
    skill_dir.mkdir(parents=True)
    # name mismatches dir name (`wrong` != `badmeta`) — fails the
    # source-dirname == registry slug invariant in validate_skill.
    skill_dir.joinpath("_meta.yaml").write_text(
        "name: wrong\n"
        "description: Intentional schema-violation fixture.\n"
        "version: 0.1.0\n"
        "compatibility:\n"
        "  openclaw: true\n"
        "  hermes: true\n"
        "  zeroclaw: true\n"
    )
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: wrong\ndescription: same\n---\nbody\n"
    )
    return root
