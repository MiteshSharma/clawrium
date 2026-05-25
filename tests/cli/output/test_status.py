"""Tests for the STATUS column formatter."""

import io

import pytest

from clawrium.cli.output.status import _COLORS, format_status


@pytest.mark.parametrize("token", list(_COLORS))
def test_force_color_emits_ansi(token: str) -> None:
    out = format_status(token, force_color=True)
    assert out.startswith("\x1b[")
    assert out.endswith("\x1b[0m")
    assert token in out


def test_non_tty_emits_raw_token() -> None:
    stream = io.StringIO()  # not a TTY
    out = format_status("running", stream=stream)
    assert out == "running"


def test_no_color_env_blocks_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    out = format_status("running", force_color=True)
    assert out == "running"


def test_unknown_token_passes_through() -> None:
    out = format_status("nonsense-token", force_color=True)
    assert out == "nonsense-token"


def test_known_vocabulary_complete() -> None:
    expected = {
        "running",
        "degraded",
        "stopped",
        "pending",
        "onboarding",
        "ready",
        "installing",
        "failed",
        "unknown",
    }
    assert set(_COLORS) == expected
