"""Issue #426 — sync_agent materializes `agent.providers` (attach list)
into `config.provider` (Ansible-rendered dict) and advances the
onboarding state machine through the `providers` stage when needed.

These tests exercise `core/lifecycle.sync_agent` directly with
`configure_agent` mocked out — so the contract under test is exactly the
shape of the `config_data` argument the bridge feeds into the
remote-push call.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from clawrium.core.lifecycle import LifecycleError, sync_agent


def _host_with_agent(
    *,
    state: str = "pending",
    providers_attached: list[str] | None = None,
    config: dict | None = None,
) -> dict:
    """Build a minimal host record carrying one openclaw agent."""
    agent: dict = {
        "type": "openclaw",
        "onboarding": {"state": state},
        "config": {"gateway": {"port": 40000}} if config is None else config,
    }
    if providers_attached is not None:
        agent["providers"] = providers_attached
    return {
        "hostname": "192.168.1.100",
        "key_id": "test",
        "agent_name": "xclm",
        "port": 22,
        "agents": {"opc-work": agent},
    }


def _ollama_provider_record() -> dict:
    return {
        "name": "local-inx",
        "type": "ollama",
        "endpoint": "http://192.168.1.17:11434",
        "default_model": "qwen3-coder:30b-128k",
    }


def test_sync_materializes_attached_provider_into_config():
    """Happy path: agent.providers=["local-inx"] + state=pending →
    sync overlays the provider record from providers.json onto
    config.provider before pushing.
    """
    host = _host_with_agent(state="pending", providers_attached=["local-inx"])

    captured: dict = {}

    def fake_configure(hostname, claw_name, config_data, **kwargs):
        captured["config_data"] = config_data
        captured["claw_name"] = claw_name
        return (True, None)

    with (
        patch("clawrium.core.lifecycle.get_host", return_value=host),
        patch(
            "clawrium.core.providers.storage.get_provider",
            return_value=_ollama_provider_record(),
        ),
        patch("clawrium.core.onboarding.complete_stage") as mock_complete,
        patch("clawrium.core.lifecycle.configure_agent", side_effect=fake_configure),
    ):
        result = sync_agent("192.168.1.100", "openclaw")

    assert result["success"] is True
    provider = captured["config_data"]["provider"]
    assert provider["name"] == "local-inx"
    assert provider["type"] == "ollama"
    assert provider["endpoint"] == "http://192.168.1.17:11434"
    assert provider["default_model"] == "qwen3-coder:30b-128k"
    # State must have been advanced through providers stage so the
    # PENDING-rejection check downstream passes.
    mock_complete.assert_called_once()
    call_args = mock_complete.call_args
    assert call_args.args[2] == "providers"
    assert call_args.args[4] == {"provider_id": "local-inx"}


def test_sync_carries_optional_provider_fields():
    """context_window / max_tokens flow through when present on the
    provider record."""
    host = _host_with_agent(state="ready", providers_attached=["maurice"])
    rec = {
        "name": "maurice",
        "type": "openrouter",
        "endpoint": "https://openrouter.ai/api/v1",
        "default_model": "z-ai/glm-4.5-air",
        "context_window": 128000,
        "max_tokens": 4096,
    }

    captured: dict = {}

    def fake_configure(hostname, claw_name, config_data, **kwargs):
        captured["config_data"] = config_data
        return (True, None)

    with (
        patch("clawrium.core.lifecycle.get_host", return_value=host),
        patch("clawrium.core.providers.storage.get_provider", return_value=rec),
        patch("clawrium.core.lifecycle.configure_agent", side_effect=fake_configure),
    ):
        result = sync_agent("192.168.1.100", "openclaw")

    assert result["success"] is True
    provider = captured["config_data"]["provider"]
    assert provider["context_window"] == 128000
    assert provider["max_tokens"] == 4096


def test_sync_legacy_agent_without_attachment_unchanged():
    """Regression guard: agents installed before #426 (no
    `agent.providers` field, `config.provider` already populated by
    the legacy `clm` flow) must sync without the bridge interfering."""
    legacy_config = {
        "gateway": {"port": 40000},
        "provider": {
            "name": "legacy-provider",
            "type": "ollama",
            "endpoint": "http://localhost:11434",
            "default_model": "llama3",
        },
    }
    host = _host_with_agent(state="ready", config=legacy_config)
    # No `providers` key at all on the agent record.
    assert "providers" not in host["agents"]["opc-work"]

    captured: dict = {}

    def fake_configure(hostname, claw_name, config_data, **kwargs):
        captured["config_data"] = config_data
        return (True, None)

    with (
        patch("clawrium.core.lifecycle.get_host", return_value=host),
        patch("clawrium.core.lifecycle.configure_agent", side_effect=fake_configure),
    ):
        result = sync_agent("192.168.1.100", "openclaw")

    assert result["success"] is True
    # Legacy provider block flows through untouched.
    assert captured["config_data"]["provider"]["name"] == "legacy-provider"


def test_sync_unknown_attached_provider_errors_cleanly():
    """Provider name in `agent.providers` not present in providers.json
    must surface a clear LifecycleError, not a NoneType crash."""
    host = _host_with_agent(state="pending", providers_attached=["ghost"])

    with (
        patch("clawrium.core.lifecycle.get_host", return_value=host),
        patch("clawrium.core.providers.storage.get_provider", return_value=None),
    ):
        with pytest.raises(LifecycleError) as exc_info:
            sync_agent("192.168.1.100", "openclaw")

    assert "ghost" in str(exc_info.value)
    assert "not registered" in str(exc_info.value)


def test_sync_rejects_multi_provider_hand_edit():
    """Defense-in-depth: hosts.json hand-edited to have two attached
    providers must fail loudly rather than silently picking index 0."""
    host = _host_with_agent(state="ready", providers_attached=["one", "two"])

    with patch("clawrium.core.lifecycle.get_host", return_value=host):
        with pytest.raises(LifecycleError) as exc_info:
            sync_agent("192.168.1.100", "openclaw")

    assert "single-provider invariant" in str(exc_info.value)


def test_sync_pending_without_attachment_keeps_legacy_error():
    """Agent with no provider attached AND state=pending must keep
    erroring at the PENDING-rejection gate so users still get a clear
    signal that the agent needs configuration."""
    host = _host_with_agent(state="pending")
    assert "providers" not in host["agents"]["opc-work"]

    with patch("clawrium.core.lifecycle.get_host", return_value=host):
        with pytest.raises(LifecycleError) as exc_info:
            sync_agent("192.168.1.100", "openclaw")

    assert "onboarding not started" in str(exc_info.value)
    # Error message now points at the new attach surface, not legacy clm.
    assert "clawctl agent provider attach" in str(exc_info.value)
