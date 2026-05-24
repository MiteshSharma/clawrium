"""Tests for `clawctl agent open` (ATX iter-1 B6).

Mocks `core.web_ui.resolve` + `webbrowser.open` so no real browser
launches under pytest.
"""

from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def test_open_no_web_ui_errors_clean(fleet_dir, monkeypatch) -> None:
    monkeypatch.setattr(
        "clawrium.cli.clawctl.agent.open.resolve_web_ui", lambda _: None
    )
    result = runner.invoke(app, ["agent", "open", "wise-hypatia"])
    assert result.exit_code != 0
    assert "no web UI" in result.output


def test_open_print_url_local_host_skips_tunnel(fleet_dir, monkeypatch) -> None:
    resolved = SimpleNamespace(host="127.0.0.1", remote_port=12345)
    monkeypatch.setattr(
        "clawrium.cli.clawctl.agent.open.resolve_web_ui", lambda _: resolved
    )
    # If webbrowser.open is hit unexpectedly, fail loudly.
    called = []
    monkeypatch.setattr("webbrowser.open", lambda url: called.append(url))
    result = runner.invoke(app, ["agent", "open", "wise-hypatia", "--print-url"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:12345" in result.output
    assert called == []  # --print-url skips the browser


def test_open_remote_host_uses_tunnel(fleet_dir, monkeypatch) -> None:
    resolved = SimpleNamespace(host="10.0.0.1", remote_port=9999)
    monkeypatch.setattr(
        "clawrium.cli.clawctl.agent.open.resolve_web_ui", lambda _: resolved
    )
    monkeypatch.setattr("clawrium.core.web_ui_tunnel.ensure", lambda _agent_key: 45678)
    monkeypatch.setattr("webbrowser.open", lambda url: None)
    result = runner.invoke(app, ["agent", "open", "wise-hypatia"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:45678" in result.output


def test_open_unknown_agent_errors(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "open", "no-such-agent"])
    assert result.exit_code != 0
    assert "not found" in result.output
