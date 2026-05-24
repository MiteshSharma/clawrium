"""Tests for `clawctl agent chat` (ATX iter-1 B8)."""

from __future__ import annotations

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_chat_unknown_agent_errors(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "chat", "no-such-agent"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_chat_once_uses_canonical_placeholder(fleet_dir) -> None:
    """ATX iter-1 W6: placeholder must use canonical `Not implemented:` line."""
    result = runner.invoke(app, ["agent", "chat", "wise-hypatia", "--once", "hi"])
    assert result.exit_code == 0
    assert "Not implemented: agent chat --once" in result.output


def test_chat_without_once_invokes_backend(fleet_dir, monkeypatch) -> None:
    called: list[dict] = []

    def fake_chat(**kwargs):
        called.append(kwargs)

    monkeypatch.setattr("clawrium.cli.chat.chat", fake_chat)
    result = runner.invoke(app, ["agent", "chat", "wise-hypatia"])
    assert result.exit_code == 0
    assert len(called) == 1
    assert called[0]["agent_name"] == "wise-hypatia"
