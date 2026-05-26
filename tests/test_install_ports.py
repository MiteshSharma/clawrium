# Tests for issue #533: per-instance listener ports across all agent types.
#
# Covers the shared `_pick_per_instance_port` helper plus the three call sites
# (hermes dashboard, hermes api_server, openclaw/zeroclaw gateway). The dashboard
# regression suite already in tests/test_install.py exercises the install-time
# wiring; this file focuses on the new helper directly and the two new ports.

import hashlib

import pytest

from clawrium.core.install import InstallationError, _pick_per_instance_port


# ---------------------------------------------------------------------------
# Direct unit tests for the helper
# ---------------------------------------------------------------------------


def _agent(port_path: tuple[str, ...], port: int) -> dict:
    """Build an agent record dict that nests `port` under `config.<port_path>`."""
    record: dict = {"type": "hermes", "status": "installed", "config": {}}
    node = record["config"]
    for seg in port_path[:-1]:
        node[seg] = {}
        node = node[seg]
    node[port_path[-1]] = port
    return record


def test_helper_returns_preserved_port_in_window():
    host = {"hostname": "h", "agents": {}}
    got = _pick_per_instance_port(
        host, "anything", base=8600, span=100,
        port_field_path=("api_server", "port"),
        preserved_port=8650,
    )
    assert got == 8650


def test_helper_rejects_preserved_port_outside_window():
    host = {"hostname": "h", "agents": {}}
    # 9999 is outside 8600..8699 — must be ignored, helper picks via hash.
    got = _pick_per_instance_port(
        host, "agent-x", base=8600, span=100,
        port_field_path=("api_server", "port"),
        preserved_port=9999,
    )
    assert 8600 <= got <= 8699
    expected = 8600 + (int(hashlib.md5(b"agent-x").hexdigest(), 16) % 100)
    assert got == expected


def test_helper_hash_collision_walks_to_next_free_port():
    # Pre-occupy the natural hash slot for "agent-a".
    natural = 8600 + (int(hashlib.md5(b"agent-a").hexdigest(), 16) % 100)
    host = {
        "hostname": "h",
        "agents": {
            "agent-other": _agent(("api_server", "port"), natural),
        },
    }
    got = _pick_per_instance_port(
        host, "agent-a", base=8600, span=100,
        port_field_path=("api_server", "port"),
    )
    assert got != natural
    assert 8600 <= got <= 8699


def test_helper_wraps_at_top_of_window():
    # Park the requesting agent's natural slot at 8699 so the walk has to wrap.
    name = "wrap-me"
    natural = 8600 + (int(hashlib.md5(name.encode()).hexdigest(), 16) % 100)
    # Force the candidate to start at the top by making natural=8699 if possible.
    # Instead of brute-forcing the name, occupy `natural` and the run will walk
    # forward; either way collision walk must produce a port in the window.
    host = {
        "hostname": "h",
        "agents": {
            "occupier": _agent(("api_server", "port"), natural),
        },
    }
    got = _pick_per_instance_port(
        host, name, base=8600, span=100,
        port_field_path=("api_server", "port"),
    )
    assert 8600 <= got <= 8699
    assert got != natural


def test_helper_raises_when_pool_exhausted():
    host = {
        "hostname": "h",
        "agents": {
            f"occ-{p}": _agent(("api_server", "port"), p)
            for p in range(8600, 8700)
        },
    }
    with pytest.raises(InstallationError, match="[Pp]ool exhausted"):
        _pick_per_instance_port(
            host, "new", base=8600, span=100,
            port_field_path=("api_server", "port"),
        )


def test_helper_ignores_self_in_collision_set():
    # Self-agent's own persisted port must not block self.
    host = {
        "hostname": "h",
        "agents": {
            "myself": _agent(("api_server", "port"), 8650),
        },
    }
    # No preserved_port hint, but "myself" should still get a clean pick
    # without colliding with its own old record.
    got = _pick_per_instance_port(
        host, "myself", base=8600, span=100,
        port_field_path=("api_server", "port"),
    )
    assert 8600 <= got <= 8699


def test_helper_ignores_other_agent_types_at_wrong_path():
    # A peer that stores a port under config.gateway.port must NOT poison
    # the api_server collision set.
    host = {
        "hostname": "h",
        "agents": {
            "openclaw-peer": _agent(("gateway", "port"), 8650),
        },
    }
    got = _pick_per_instance_port(
        host, "hermes-new", base=8600, span=100,
        port_field_path=("api_server", "port"),
    )
    # Peer's gateway.port=8650 must not register as a collision.
    expected = 8600 + (int(hashlib.md5(b"hermes-new").hexdigest(), 16) % 100)
    assert got == expected


# ---------------------------------------------------------------------------
# Install-time integration: hermes api_server port
# ---------------------------------------------------------------------------


def test_install_hermes_api_server_port_assigned_and_persisted(monkeypatch, tmp_path):
    from tests.test_install import _hermes_install_scaffold

    run_installation, get_host, _c, _a = _hermes_install_scaffold(
        monkeypatch, tmp_path
    )
    result = run_installation("hermes", "test-host", name="hermes-api")
    assert result["success"] is True

    api = get_host()["agents"]["hermes-api"]["config"]["api_server"]
    assert 8600 <= api["port"] <= 8699
    expected = 8600 + (int(hashlib.md5(b"hermes-api").hexdigest(), 16) % 100)
    assert api["port"] == expected


def test_install_hermes_api_server_port_preserved_on_reinstall(monkeypatch, tmp_path):
    from tests.test_install import _hermes_install_scaffold

    custom_port = 8677  # in-window but not the deterministic-hash value
    preexisting = {
        "hermes-keep": {
            "type": "hermes",
            "version": "2026.5.7",
            "status": "installed",
            "installed_at": "2026-01-01T00:00:00+00:00",
            "config": {
                "api_server": {
                    "enabled": True,
                    "host": "0.0.0.0",
                    "port": custom_port,
                },
                "dashboard": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 45500,
                },
            },
        }
    }
    run_installation, get_host, _c, _a = _hermes_install_scaffold(
        monkeypatch, tmp_path, preexisting_agents=preexisting,
    )
    result = run_installation("hermes", "test-host", name="hermes-keep")
    assert result["success"] is True

    api = get_host()["agents"]["hermes-keep"]["config"]["api_server"]
    assert api["port"] == custom_port


def test_install_hermes_api_server_port_grandfathers_legacy_8642(monkeypatch, tmp_path):
    """Pre-#533 hermes agents persisted port=8642. Reinstall must keep it,
    not relocate them into the new 8600..8699 window."""
    from tests.test_install import _hermes_install_scaffold

    preexisting = {
        "espresso-like": {
            "type": "hermes",
            "version": "2026.5.7",
            "status": "installed",
            "installed_at": "2026-01-01T00:00:00+00:00",
            "config": {
                "api_server": {
                    "enabled": True,
                    "host": "0.0.0.0",
                    "port": 8642,
                },
                "dashboard": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 45500,
                },
            },
        }
    }
    run_installation, get_host, _c, _a = _hermes_install_scaffold(
        monkeypatch, tmp_path, preexisting_agents=preexisting,
    )
    result = run_installation("hermes", "test-host", name="espresso-like")
    assert result["success"] is True
    assert get_host()["agents"]["espresso-like"]["config"]["api_server"]["port"] == 8642


def test_install_two_hermes_sequential_get_distinct_ports(monkeypatch, tmp_path):
    """ATX iter-1 test-coverage gap: install two hermes agents back-to-back
    on the same host and assert both api_server and dashboard ports are
    distinct. This catches both the lock-coverage regression (W2) and the
    in-progress-record-visibility regression (W3-related).
    """
    from tests.test_install import _hermes_install_scaffold

    run_installation, get_host, _c, _a = _hermes_install_scaffold(
        monkeypatch, tmp_path,
    )

    result_a = run_installation("hermes", "test-host", name="hermes-aaa")
    assert result_a["success"] is True
    api_a = get_host()["agents"]["hermes-aaa"]["config"]["api_server"]["port"]
    dash_a = get_host()["agents"]["hermes-aaa"]["config"]["dashboard"]["port"]

    result_b = run_installation("hermes", "test-host", name="hermes-bbb")
    assert result_b["success"] is True
    api_b = get_host()["agents"]["hermes-bbb"]["config"]["api_server"]["port"]
    dash_b = get_host()["agents"]["hermes-bbb"]["config"]["dashboard"]["port"]

    assert api_a != api_b
    assert dash_a != dash_b
    assert 8600 <= api_a <= 8699
    assert 8600 <= api_b <= 8699
    assert 45000 <= dash_a <= 46999
    assert 45000 <= dash_b <= 46999


def test_install_hermes_does_not_persist_gateway_block(monkeypatch, tmp_path):
    """ATX iter-2 W4: hermes installs must not write `config.gateway` to
    hosts.json — gateway config is only meaningful for openclaw/zeroclaw.
    A regression unconditionally building the gateway block would silently
    consume the 40000..41999 pool with ghost allocations."""
    from tests.test_install import _hermes_install_scaffold

    run_installation, get_host, _c, _a = _hermes_install_scaffold(
        monkeypatch, tmp_path,
    )
    result = run_installation("hermes", "test-host", name="hermes-nogw")
    assert result["success"] is True
    assert "gateway" not in get_host()["agents"]["hermes-nogw"]["config"]


def test_install_hermes_api_server_port_collision_picks_different(monkeypatch, tmp_path):
    """Two hermes installs on the same host get distinct api_server ports."""
    from tests.test_install import _hermes_install_scaffold

    name_a = "hermes-aa"
    natural_a = 8600 + (int(hashlib.md5(name_a.encode()).hexdigest(), 16) % 100)
    preexisting = {
        "first": {
            "type": "hermes",
            "version": "2026.5.7",
            "status": "installed",
            "config": {
                "api_server": {
                    "enabled": True,
                    "host": "0.0.0.0",
                    "port": natural_a,
                },
                "dashboard": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 45500,
                },
            },
        }
    }
    run_installation, get_host, _c, _a = _hermes_install_scaffold(
        monkeypatch, tmp_path, preexisting_agents=preexisting,
    )
    result = run_installation("hermes", "test-host", name=name_a)
    assert result["success"] is True
    new_port = get_host()["agents"][name_a]["config"]["api_server"]["port"]
    assert new_port != natural_a
    assert 8600 <= new_port <= 8699
