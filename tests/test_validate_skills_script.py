"""Tests for `scripts/validate_skills.py` — the CI catalog validator.

Phase 6 exit criterion: "CI rejects invalid-fixture PR; accepts
valid-fixture PR." These tests express that contract directly by
building fixture catalogs in `tmp_path` and running the validator
against them. The real `skills/` tree is exercised by the
`make test` integration check below.

Each fixture is the smallest possible catalog that still triggers the
exact failure we care about. We assert on:

- A non-empty failure list (the validator reports the issue).
- The specific failure message substring (so a future regression that
  silently swallows the check fails this test, not just refactors).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from textwrap import dedent


# scripts/validate_skills.py is not a package — import it via importlib
# so we can call validate_catalog() directly. The CI workflow exercises
# the `__main__` path separately via `python scripts/validate_skills.py`.
_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "validate_skills.py"
)
_spec = importlib.util.spec_from_file_location("validate_skills", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
validate_skills_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_skills"] = validate_skills_mod
_spec.loader.exec_module(validate_skills_mod)

validate_catalog = validate_skills_mod.validate_catalog
ValidationFailure = validate_skills_mod.ValidationFailure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_schemas(root: Path) -> None:
    """Copy the real `_schema/` tree into a fixture catalog. Validator
    behavior depends on the actual schemas — re-defining them inline
    would let drift in the production schemas silently break this test
    suite."""
    real_schema = (
        Path(__file__).resolve().parent.parent / "skills" / "_schema"
    )
    schema_dir = root / "_schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "clawrium.schema.json").write_text(
        (real_schema / "clawrium.schema.json").read_text()
    )
    native_dir = schema_dir / "native"
    native_dir.mkdir(exist_ok=True)
    for claw in ("openclaw", "hermes", "zeroclaw"):
        (native_dir / f"{claw}.schema.json").write_text(
            (real_schema / "native" / f"{claw}.schema.json").read_text()
        )


def _empty_registries(root: Path) -> None:
    for reg in ("clawrium", "openclaw", "hermes", "zeroclaw"):
        (root / reg).mkdir(parents=True, exist_ok=True)


def _build_fixture(root: Path) -> None:
    _write_schemas(root)
    _empty_registries(root)


def _has_failure(
    failures: list[ValidationFailure], path_part: str, message_part: str
) -> bool:
    return any(
        path_part in str(failure.path) and message_part in failure.message
        for failure in failures
    )


_VALID_META = dedent(
    """\
    name: tdd
    description: A test skill.
    version: 0.1.0
    compatibility:
      openclaw: true
      hermes: true
      zeroclaw: true
    """
)
_VALID_SKILL_MD = dedent(
    """\
    ---
    name: tdd
    description: A test skill.
    ---

    # Body
    """
)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_catalog_passes(tmp_path):
    _build_fixture(tmp_path)
    skill = tmp_path / "clawrium" / "tdd"
    skill.mkdir()
    (skill / "_meta.yaml").write_text(_VALID_META)
    (skill / "SKILL.md").write_text(_VALID_SKILL_MD)

    assert validate_catalog(tmp_path) == []


def test_native_skill_passes(tmp_path):
    _build_fixture(tmp_path)
    skill = tmp_path / "openclaw" / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        dedent(
            """\
            ---
            name: demo
            description: An openclaw-native demo skill.
            ---

            # Body
            """
        )
    )

    assert validate_catalog(tmp_path) == []


# ---------------------------------------------------------------------------
# Path-traversal fixtures
# ---------------------------------------------------------------------------


def test_path_traversal_via_bad_dirname_rejected(tmp_path):
    """A directory whose name fails the slug rule (incl. leading dots
    and dot-segments) is rejected before any file read. Even though
    Path() would never resolve `..` literally as a child entry, the
    same regex catches `evil-..` style attempts as well."""
    _build_fixture(tmp_path)
    # We can't literally create a directory named ".." (it resolves up),
    # but the slug rule catches the broader class of forbidden names:
    # dotfiles, dot-prefixed dirs, and anything not matching kebab-case.
    (tmp_path / "clawrium" / ".hidden").mkdir()

    failures = validate_catalog(tmp_path)
    assert _has_failure(
        failures, ".hidden", "violates the slug rule"
    ), failures


def test_path_traversal_via_symlink_rejected(tmp_path):
    """A symlink inside a skill directory is rejected regardless of
    where it points. Skills are flat content; symlinks are not."""
    _build_fixture(tmp_path)
    skill = tmp_path / "clawrium" / "tdd"
    skill.mkdir()
    (skill / "_meta.yaml").write_text(_VALID_META)
    (skill / "SKILL.md").write_text(_VALID_SKILL_MD)

    # The symlink target itself is benign (/etc/hostname); the rule is
    # "no symlinks at all," so target choice is irrelevant to the test.
    evil = skill / "leak"
    evil.symlink_to("/etc/hostname")

    failures = validate_catalog(tmp_path)
    assert _has_failure(failures, "leak", "symlinks are not allowed"), failures


def test_unexpected_top_level_directory_rejected(tmp_path):
    """Anything at skills/ root that isn't `_schema`, a known registry,
    or README.md is rejected — keeps the catalog tree from accumulating
    drive-by directories."""
    _build_fixture(tmp_path)
    (tmp_path / "external").mkdir()

    failures = validate_catalog(tmp_path)
    assert _has_failure(failures, "external", "unexpected top-level"), failures


# ---------------------------------------------------------------------------
# Schema-mismatch fixtures
# ---------------------------------------------------------------------------


def test_meta_yaml_under_native_registry_rejected(tmp_path):
    """A `_meta.yaml` under skills/<claw>/ is the classic schema-mismatch
    signal — a clawrium-shaped skill mis-placed under a native registry.
    The validator surfaces this even if the SKILL.md frontmatter alone
    would have passed the lenient native schema."""
    _build_fixture(tmp_path)
    skill = tmp_path / "openclaw" / "demo"
    skill.mkdir()
    (skill / "_meta.yaml").write_text(_VALID_META)
    (skill / "SKILL.md").write_text(
        dedent(
            """\
            ---
            name: demo
            description: An openclaw demo with a stray _meta.yaml.
            ---

            # Body
            """
        )
    )

    failures = validate_catalog(tmp_path)
    assert _has_failure(
        failures,
        "_meta.yaml",
        "only valid under skills/clawrium/",
    ), failures


def test_clawrium_keys_in_native_frontmatter_rejected(tmp_path):
    """Native schemas are `additionalProperties: true`. If we did NOT
    explicitly reject clawrium-only keys, a contributor could paste a
    clawrium frontmatter under skills/zeroclaw/ and have it silently
    pass — defeating the dual-schema guarantee."""
    _build_fixture(tmp_path)
    skill = tmp_path / "zeroclaw" / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        dedent(
            """\
            ---
            name: demo
            description: A zeroclaw skill with a stray compatibility block.
            compatibility:
              openclaw: true
              hermes: true
              zeroclaw: true
            ---

            # Body
            """
        )
    )

    failures = validate_catalog(tmp_path)
    assert _has_failure(
        failures,
        "SKILL.md",
        "clawrium-only keys",
    ), failures


def test_clawrium_name_mismatch_rejected(tmp_path):
    """The source-dirname == registry-slug invariant (Phase 0 finding).
    Zeroclaw uses the source dirname for `remove`; if `_meta.yaml.name`
    drifts from the directory name, downstream uninstalls break."""
    _build_fixture(tmp_path)
    skill = tmp_path / "clawrium" / "tdd"
    skill.mkdir()
    (skill / "_meta.yaml").write_text(
        dedent(
            """\
            name: not-tdd
            description: Mismatched name.
            version: 0.1.0
            compatibility:
              openclaw: true
              hermes: true
              zeroclaw: true
            """
        )
    )
    (skill / "SKILL.md").write_text(_VALID_SKILL_MD)

    failures = validate_catalog(tmp_path)
    assert _has_failure(
        failures,
        "_meta.yaml",
        "must equal directory name",
    ), failures


def test_native_skill_name_mismatch_rejected(tmp_path):
    _build_fixture(tmp_path)
    skill = tmp_path / "hermes" / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        dedent(
            """\
            ---
            name: wrong
            description: Mismatched name.
            ---

            # Body
            """
        )
    )

    failures = validate_catalog(tmp_path)
    assert _has_failure(
        failures,
        "SKILL.md",
        "must equal directory name",
    ), failures


def test_missing_required_field_rejected(tmp_path):
    """Schema-required keys (e.g. clawrium `compatibility`) must trip
    the dual-schema validator. This is the same code path that
    runtime `validate_skill` exercises — we just confirm it surfaces
    from the validator script too."""
    _build_fixture(tmp_path)
    skill = tmp_path / "clawrium" / "tdd"
    skill.mkdir()
    (skill / "_meta.yaml").write_text(
        dedent(
            """\
            name: tdd
            description: Missing compatibility.
            version: 0.1.0
            """
        )
    )
    (skill / "SKILL.md").write_text(_VALID_SKILL_MD)

    failures = validate_catalog(tmp_path)
    # jsonschema renders the missing-required diagnostic via the schema
    # title; the contributor-facing message is the full schema error.
    assert any(
        "compatibility" in failure.message for failure in failures
    ), failures


def test_missing_skill_md_rejected(tmp_path):
    _build_fixture(tmp_path)
    skill = tmp_path / "clawrium" / "tdd"
    skill.mkdir()
    (skill / "_meta.yaml").write_text(_VALID_META)
    # Intentionally no SKILL.md.

    failures = validate_catalog(tmp_path)
    assert _has_failure(failures, "tdd", "missing required SKILL.md"), failures


def test_missing_frontmatter_in_native_rejected(tmp_path):
    _build_fixture(tmp_path)
    skill = tmp_path / "hermes" / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# No frontmatter\n")

    failures = validate_catalog(tmp_path)
    assert _has_failure(
        failures, "SKILL.md", "YAML frontmatter block"
    ), failures


# ---------------------------------------------------------------------------
# Integration: the real catalog must always validate
# ---------------------------------------------------------------------------


def test_real_in_repo_catalog_validates():
    """The actual skills/ tree at repo root validates. This guards
    against schema regressions slipping past PR review — if a real
    skill is broken, this test fails before CI even runs the workflow."""
    real_root = Path(__file__).resolve().parent.parent / "skills"
    assert validate_catalog(real_root) == [], (
        "The in-repo skills/ catalog does not validate. "
        "Run `python scripts/validate_skills.py` for the full report."
    )
