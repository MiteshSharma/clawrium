"""Bidi-sanitization regression tests (ATX iter-1 B1, B2).

A host alias or agent name containing U+202E in hosts.json must not
reverse-render in `describe` output. These tests assert sanitize() is
called at every f-string interpolation site in the describe paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from clawrium.cli import app

runner = CliRunner()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def malicious_fleet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fleet with U+202E embedded in user-controlled string fields."""
    config_dir = tmp_path / "clawrium"
    config_dir.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    bidi = "‮"
    hosts = [
        {
            "hostname": "10.0.0.99",
            "key_id": "10.0.0.99",
            "port": 22,
            "user": "alice",
            "auth_method": "key",
            "alias": f"wolf{bidi}i",
            "aliases": [f"wolf{bidi}i"],
            "addresses": [
                {
                    "address": "10.0.0.99",
                    "is_primary": True,
                    "label": f"primary{bidi}",
                    "added_at": _utcnow(),
                }
            ],
            "metadata": {
                "added_at": _utcnow(),
                "last_seen": _utcnow(),
                "labels": {f"k{bidi}ey": f"v{bidi}al"},
            },
            "hardware": {},
            "agents": {
                "openclaw": {
                    "type": "openclaw",
                    "agent_name": f"evil{bidi}name",
                    "version": "0.4.2",
                    "installed_at": _utcnow(),
                    "status": "installed",
                    "onboarding": {"state": "ready", "stages": {}},
                    "config": {
                        "providers": {f"p{bidi}rovider": {}},
                        "skills": [f"clawrium/{bidi}evil"],
                        "integrations": {f"github{bidi}": "configured"},
                    },
                }
            },
        }
    ]
    (config_dir / "hosts.json").write_text(json.dumps(hosts))
    return config_dir


def test_host_describe_strips_bidi(malicious_fleet) -> None:
    result = runner.invoke(app, ["host", "describe", "wolf‮i"])
    assert result.exit_code == 0
    assert "‮" not in result.output, (
        "bidi override leaked through describe — ATX iter-1 B1 regression"
    )


def test_agent_describe_strips_bidi(malicious_fleet) -> None:
    result = runner.invoke(app, ["agent", "describe", "evil‮name"])
    assert result.exit_code == 0
    assert "‮" not in result.output, (
        "bidi override leaked through agent describe — ATX iter-1 B1 regression"
    )


def test_agent_registry_describe_strips_bidi_in_argname(fleet_dir) -> None:
    # Run with a known-good type but pass the raw arg with U+202E — the
    # error path must also strip bidi before echoing the unknown-type
    # name back at the user.
    result = runner.invoke(app, ["agent", "registry", "describe", "open‮claw"])
    # Either exits non-zero (unknown type) or echoes the type name — in
    # both cases the bidi char MUST NOT appear in the output stream.
    assert "‮" not in result.output
