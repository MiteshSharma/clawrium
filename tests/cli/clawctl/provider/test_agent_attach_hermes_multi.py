"""Issue #612 — hermes multi-provider attach/detach via clawctl.

Covers the CLI surface added under parent #589:

- `--role primary` required for the first attach on hermes
- attach without `--role` rejected with a remediation hint
- second `--role <aux>` attach succeeds and shows up in `get`
- `get` table renders `name`, `role`, `model` columns
- `detach` of primary is rejected while aux attachments remain
- non-hermes still rejects the second attach with the verbatim
  `single-provider invariant` phrase pinned from
  `core/provider_attachments.validate()`
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def _create_provider(name: str, ptype: str = "anthropic") -> None:
    result = runner.invoke(
        app,
        [
            "provider",
            "registry",
            "create",
            name,
            "--type",
            ptype,
            "--api-key",
            "k",
        ],
    )
    assert result.exit_code == 0, result.output


def test_hermes_attach_without_role_is_rejected(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    result = runner.invoke(
        app, ["agent", "provider", "attach", "anth", "--agent", "sage-hermes"]
    )
    assert result.exit_code != 0, result.output
    assert "--role is required" in result.output
    # Hint must surface primary as the canonical first-attach role.
    assert "primary" in result.output


def test_hermes_attach_primary_succeeds(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    result = runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "attached" in result.output
    assert "primary" in result.output


def test_hermes_attach_aux_after_primary(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    _create_provider("openrt", ptype="openrouter")
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    result = runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "openrt",
            "--agent",
            "sage-hermes",
            "--role",
            "vision",
        ],
    )
    assert result.exit_code == 0, result.output

    listed = runner.invoke(
        app, ["agent", "provider", "get", "--agent", "sage-hermes", "-o", "json"]
    )
    data = json.loads(listed.output)
    by_name = {p["name"]: p for p in data}
    assert by_name["anth"]["role"] == "primary"
    assert by_name["openrt"]["role"] == "vision"


def test_hermes_attach_invalid_role(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    result = runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "not-a-real-slot",
        ],
    )
    assert result.exit_code != 0
    assert "invalid --role" in result.output


def test_hermes_attach_duplicate_primary_rejected(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    _create_provider("openrt", ptype="openrouter")
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    # Attaching a second primary must fail (validate() enforces exactly
    # one primary).
    result = runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "openrt",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    assert result.exit_code != 0, result.output


def test_hermes_attach_same_name_with_different_role_rejected(
    hermes_fleet_dir, stdin_not_tty
) -> None:
    _create_provider("anth")
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    result = runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "vision",
        ],
    )
    assert result.exit_code != 0
    assert "already attached" in result.output


def test_hermes_attach_idempotent_same_role(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    result = runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    assert result.exit_code == 0
    assert "already attached" in result.output


def test_hermes_get_table_renders_role_and_model_columns(
    hermes_fleet_dir, stdin_not_tty
) -> None:
    _create_provider("anth")
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    result = runner.invoke(
        app, ["agent", "provider", "get", "--agent", "sage-hermes"]
    )
    assert result.exit_code == 0, result.output
    assert "ROLE" in result.output
    assert "MODEL" in result.output


def test_hermes_detach_primary_blocked_when_aux_present(
    hermes_fleet_dir, stdin_not_tty
) -> None:
    _create_provider("anth")
    _create_provider("openrt", ptype="openrouter")
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "openrt",
            "--agent",
            "sage-hermes",
            "--role",
            "vision",
        ],
    )
    result = runner.invoke(
        app,
        ["agent", "provider", "detach", "anth", "--agent", "sage-hermes"],
    )
    assert result.exit_code != 0, result.output
    assert "primary" in result.output
    # Hint should mention detaching aux first.
    assert "openrt" in result.output


def test_hermes_detach_primary_succeeds_when_alone(
    hermes_fleet_dir, stdin_not_tty
) -> None:
    _create_provider("anth")
    runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "sage-hermes",
            "--role",
            "primary",
        ],
    )
    result = runner.invoke(
        app,
        ["agent", "provider", "detach", "anth", "--agent", "sage-hermes"],
    )
    assert result.exit_code == 0, result.output


def test_hermes_detach_aux_then_primary(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    _create_provider("openrt", ptype="openrouter")
    for args in (
        ["anth", "--role", "primary"],
        ["openrt", "--role", "vision"],
    ):
        runner.invoke(
            app,
            ["agent", "provider", "attach", args[0], "--agent", "sage-hermes"]
            + args[1:],
        )
    # Detach aux first, then primary should succeed.
    aux = runner.invoke(
        app,
        ["agent", "provider", "detach", "openrt", "--agent", "sage-hermes"],
    )
    assert aux.exit_code == 0
    primary = runner.invoke(
        app,
        ["agent", "provider", "detach", "anth", "--agent", "sage-hermes"],
    )
    assert primary.exit_code == 0


def test_non_hermes_rejects_role_flag(hermes_fleet_dir, stdin_not_tty) -> None:
    _create_provider("anth")
    result = runner.invoke(
        app,
        [
            "agent",
            "provider",
            "attach",
            "anth",
            "--agent",
            "wise-hypatia",
            "--role",
            "primary",
        ],
    )
    assert result.exit_code != 0
    assert "--role" in result.output


def test_non_hermes_singleton_invariant_preserved(
    hermes_fleet_dir, stdin_not_tty
) -> None:
    """The verbatim `single-provider invariant` phrase from
    provider_attachments.validate() is pinned by docs + tests; the
    refactor must not regress the existing UX on zeroclaw/openclaw.

    The UX on the second-attach path is delivered via the
    `already has provider` clawctl-level error (the same message the
    pre-#612 code emitted) — the verbatim phrase remains the one
    `validate()` raises if attachments are ever forced past the CLI
    guard (e.g., by hand-editing hosts.json).
    """
    from clawrium.core.provider_attachments import AttachmentError, validate
    import pytest

    _create_provider("anth")
    _create_provider("openrt", ptype="openrouter")
    first = runner.invoke(
        app,
        ["agent", "provider", "attach", "anth", "--agent", "wise-hypatia"],
    )
    assert first.exit_code == 0

    second = runner.invoke(
        app,
        ["agent", "provider", "attach", "openrt", "--agent", "wise-hypatia"],
    )
    assert second.exit_code != 0
    assert "already has provider" in second.output
    assert "anth" in second.output

    # And the validate()-level phrase is still wired up exactly as docs
    # reference it.
    with pytest.raises(AttachmentError, match="single-provider invariant"):
        validate(["a", "b"], "openclaw")
