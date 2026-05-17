"""Tests for `clm skill list` and `clm skill show`."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from clawrium.cli import skill as skill_cli
from clawrium.cli.main import app
from clawrium.core import skills as core_skills
from clawrium.core.skills import Skill, SkillNotFound, SkillRef

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_schema_cache():
    """Module-level cache leaks between tests — reset on setup and teardown."""
    core_skills._SCHEMA_CACHE.clear()
    yield
    core_skills._SCHEMA_CACHE.clear()


def test_skill_list_includes_clawrium_tdd():
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0, result.output
    assert "clawrium/tdd" in result.output
    assert "Skills catalog" in result.output


def test_skill_list_filtered_to_native_registry_is_empty():
    result = runner.invoke(app, ["skill", "list", "--registry", "openclaw"])
    assert result.exit_code == 0
    assert "No skills registered" in result.output


def test_skill_list_unknown_registry_exits_nonzero():
    result = runner.invoke(app, ["skill", "list", "--registry", "bogus"])
    assert result.exit_code != 0
    assert "Unknown registry" in result.output


def test_skill_show_real_tdd():
    result = runner.invoke(app, ["skill", "show", "clawrium/tdd"])
    assert result.exit_code == 0, result.output
    assert "clawrium/tdd" in result.output
    assert "Test-Driven Development" in result.output
    assert "Metadata" in result.output
    assert "SKILL.md" in result.output


def test_skill_show_bare_name_returns_hint():
    result = runner.invoke(app, ["skill", "show", "tdd"])
    assert result.exit_code != 0
    assert "missing a registry prefix" in result.output
    # Hint should include the canonical clawrium/tdd suggestion.
    assert "clawrium/tdd" in result.output


def test_skill_show_external_source_blocked():
    result = runner.invoke(app, ["skill", "show", "https://example.com/x"])
    assert result.exit_code != 0
    assert "External skill sources are not allowed" in result.output


def test_skill_show_absolute_path_blocked():
    result = runner.invoke(app, ["skill", "show", "/tmp/foo"])
    assert result.exit_code != 0
    assert "Path-style skill sources are not allowed" in result.output


def test_skill_show_not_found():
    result = runner.invoke(app, ["skill", "show", "clawrium/no-such-skill"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_skill_show_unknown_registry_rejected():
    result = runner.invoke(app, ["skill", "show", "bogus/whatever"])
    assert result.exit_code != 0
    assert "Unknown registry" in result.output


def test_skill_list_no_args_works():
    # No --registry filter — should enumerate everything.
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0
    assert "clawrium/tdd" in result.output


def test_skill_top_level_help_lists_subcommands():
    result = runner.invoke(app, ["skill", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "show" in result.output


def test_skill_list_catches_missing_catalog(monkeypatch):
    # If the catalog itself can't be located, `clm skill list` must
    # exit non-zero with an Error: prefix — not raise a raw traceback.
    def fake_list(registry=None):
        raise SkillNotFound(
            "skills catalog not found (looked for ... and ...). "
            "Reinstall with: `uv tool install --force clawrium`."
        )

    monkeypatch.setattr(skill_cli, "list_skills", fake_list)
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code != 0
    assert "Error" in result.output
    # Rich may soft-wrap long messages — collapse whitespace before
    # asserting on substring presence.
    collapsed = " ".join(result.output.split())
    assert "skills catalog not found" in collapsed
    # Pin the reinstall hint in the message so the W-new2 addition has
    # a regression guard.
    assert "uv tool install --force clawrium" in collapsed


def test_skill_list_description_includes_real_text():
    # Strengthens the happy-path table test: assert the actual
    # description text reaches the rendered output, not just the ref.
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0
    assert "Test-Driven Development" in result.output


def test_skill_show_schema_validation_failure(monkeypatch, tmp_path):
    # Drive `clm skill show` through the SchemaValidationError catch
    # path. Builds a tmp_path catalog whose schema rejects the seed
    # skill (here: a fake whose _meta.name disagrees with dir name).
    skill_dir = tmp_path / "clawrium" / "bad"
    skill_dir.mkdir(parents=True)
    (skill_dir / "_meta.yaml").write_text(
        "\n".join(
            [
                "name: not-bad",  # mismatched on purpose
                "description: triggers slug-invariant failure",
                "version: 0.1.0",
                "compatibility:",
                "  openclaw: true",
                "  hermes: true",
                "  zeroclaw: true",
            ]
        )
        + "\n"
    )
    (skill_dir / "SKILL.md").write_text("---\nname: bad\ndescription: x\n---\nbody")

    # Copy the real schemas in so SchemaValidationError comes from the
    # production validator, not from a missing schema file.
    from pathlib import Path as _P

    repo_root = _P(core_skills.__file__).resolve().parents[3]
    real_schema_root = repo_root / "skills" / "_schema"
    dest = tmp_path / "_schema"
    dest.mkdir()
    (dest / "clawrium.schema.json").write_text(
        (real_schema_root / "clawrium.schema.json").read_text()
    )
    (dest / "native").mkdir()
    for native in ("openclaw", "hermes", "zeroclaw"):
        (dest / "native" / f"{native}.schema.json").write_text(
            (real_schema_root / "native" / f"{native}.schema.json").read_text()
        )

    monkeypatch.setattr(core_skills, "_catalog_root", lambda: tmp_path)
    # _SCHEMA_CACHE reset is handled by the autouse fixture above.

    result = runner.invoke(app, ["skill", "show", "clawrium/bad"])
    assert result.exit_code != 0
    assert "Error" in result.output
    assert "directory name" in result.output  # slug-invariant message


# --------------------------- _short_description ----------------------------


def test_short_description_real_skill():
    ref = SkillRef("clawrium", "tdd")
    result = skill_cli._short_description(ref)
    assert "Test-Driven Development" in result


def test_short_description_swallows_skill_error(monkeypatch):
    ref = SkillRef("clawrium", "ghost")

    def fake_load(_ref):
        raise SkillNotFound("nope")

    monkeypatch.setattr(skill_cli, "load_skill", fake_load)
    assert skill_cli._short_description(ref) == "?"


def test_short_description_truncates_long_text(monkeypatch):
    ref = SkillRef("clawrium", "long")
    fake = Skill(
        ref=ref,
        path=None,  # type: ignore[arg-type]
        metadata={"description": "x" * 200},
        body="",
        skill_md_frontmatter={},
    )
    monkeypatch.setattr(skill_cli, "load_skill", lambda _r: fake)
    result = skill_cli._short_description(ref)
    assert result.endswith("...")
    assert len(result) <= 80


def test_short_description_handles_non_string(monkeypatch):
    ref = SkillRef("clawrium", "weird")
    fake = Skill(
        ref=ref,
        path=None,  # type: ignore[arg-type]
        metadata={"description": 42},
        body="",
        skill_md_frontmatter={},
    )
    monkeypatch.setattr(skill_cli, "load_skill", lambda _r: fake)
    assert skill_cli._short_description(ref) == "?"


def test_short_description_handles_empty_string(monkeypatch):
    ref = SkillRef("clawrium", "empty")
    fake = Skill(
        ref=ref,
        path=None,  # type: ignore[arg-type]
        metadata={"description": "   "},
        body="",
        skill_md_frontmatter={},
    )
    monkeypatch.setattr(skill_cli, "load_skill", lambda _r: fake)
    assert skill_cli._short_description(ref) == "?"
