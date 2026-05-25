"""Tests for `clawctl agent port-forward` and `_parse_spec` (ATX iter-1 B7)."""

from __future__ import annotations

import pytest
import typer
from typer.testing import CliRunner

from clawrium.cli import app
from clawrium.cli.clawctl.agent.port_forward import _parse_spec

runner = CliRunner()


def test_parse_spec_local_remote() -> None:
    assert _parse_spec("8080:9090") == (8080, 9090)


def test_parse_spec_remote_only() -> None:
    assert _parse_spec("9090") == (None, 9090)


def test_parse_spec_empty_local_errors() -> None:
    with pytest.raises(typer.Exit):
        _parse_spec(":9090")


def test_parse_spec_non_integer_errors() -> None:
    with pytest.raises(typer.Exit):
        _parse_spec("abc:9090")


def test_parse_spec_bare_non_integer_errors() -> None:
    with pytest.raises(typer.Exit):
        _parse_spec("abc")


def test_port_forward_unknown_agent_errors(fleet_dir) -> None:
    result = runner.invoke(app, ["agent", "port-forward", "no-such-agent", "8080"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_port_forward_tunnel_failure_errors(fleet_dir, monkeypatch) -> None:
    def boom(_agent_key: str) -> int:
        raise RuntimeError("ssh-agent missing")

    monkeypatch.setattr("clawrium.core.web_ui_tunnel.ensure", boom)
    result = runner.invoke(app, ["agent", "port-forward", "wise-hypatia", "8080"])
    assert result.exit_code != 0
    assert "failed to open tunnel" in result.output


def test_port_forward_none_local_and_none_opened_errors(fleet_dir, monkeypatch) -> None:
    """ATX iter-1 W7: protect against `None` local port slipping through."""
    monkeypatch.setattr("clawrium.core.web_ui_tunnel.ensure", lambda _k: None)
    result = runner.invoke(app, ["agent", "port-forward", "wise-hypatia", "8080"])
    assert result.exit_code != 0
    assert "no local port" in result.output
