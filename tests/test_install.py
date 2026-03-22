"""Tests for installation orchestration."""

import pytest
from unittest.mock import Mock, patch


def test_install_invalid_claw_raises():
    """Test that install with invalid claw raises InstallationError."""
    from clawrium.core.install import run_installation, InstallationError

    with pytest.raises(InstallationError, match="not found"):
        run_installation("nonexistent_claw", "test-host")


def test_install_host_not_found_raises(monkeypatch):
    """Test that install with unknown host raises InstallationError."""
    from clawrium.core.install import run_installation, InstallationError

    # Mock load_manifest to succeed
    mock_manifest = {
        "name": "openclaw",
        "entries": [
            {
                "version": "0.1.0",
                "os": "ubuntu",
                "os_version": "24.04",
                "arch": "x86_64",
                "requirements": {
                    "min_memory_mb": 2048,
                    "gpu_required": False,
                    "dependencies": {"nodejs": ">=20.0.0"},
                },
            }
        ],
    }

    import clawrium.core.install
    monkeypatch.setattr(clawrium.core.install, "load_manifest", lambda x: mock_manifest)

    # Mock get_host to return None
    monkeypatch.setattr(clawrium.core.install, "get_host", lambda x: None)

    with pytest.raises(InstallationError, match="not found"):
        run_installation("openclaw", "unknown-host")


def test_install_incompatible_host_raises(monkeypatch):
    """Test that install with incompatible host raises InstallationError."""
    from clawrium.core.install import run_installation, InstallationError

    # Mock load_manifest
    mock_manifest = {
        "name": "openclaw",
        "entries": [
            {
                "version": "0.1.0",
                "os": "ubuntu",
                "os_version": "24.04",
                "arch": "x86_64",
                "requirements": {
                    "min_memory_mb": 2048,
                    "gpu_required": False,
                    "dependencies": {"nodejs": ">=20.0.0"},
                },
            }
        ],
    }

    import clawrium.core.install
    monkeypatch.setattr(clawrium.core.install, "load_manifest", lambda x: mock_manifest)

    # Mock get_host with incompatible hardware
    incompatible_host = {
        "hostname": "test-host",
        "user": "xclm",
        "port": 22,
        "hardware": {
            "architecture": "arm64",  # Wrong arch
            "os": "ubuntu",
            "os_version": "24.04",
            "memtotal_mb": 4096,
        },
    }
    monkeypatch.setattr(clawrium.core.install, "get_host", lambda x: incompatible_host)

    # Mock check_compatibility to return incompatible
    compat_result = {
        "compatible": False,
        "matched_entry": None,
        "reasons": ["Requires x86_64, host has arm64"],
    }
    monkeypatch.setattr(
        clawrium.core.install, "check_compatibility", lambda *args, **kwargs: compat_result
    )

    with pytest.raises(InstallationError, match="incompatible.*arm64"):
        run_installation("openclaw", "test-host")


def test_install_success(monkeypatch, tmp_path):
    """Test successful installation flow."""
    from clawrium.core.install import run_installation

    # Mock load_manifest
    mock_manifest = {
        "name": "openclaw",
        "entries": [
            {
                "version": "0.1.0",
                "os": "ubuntu",
                "os_version": "24.04",
                "arch": "x86_64",
                "requirements": {
                    "min_memory_mb": 2048,
                    "gpu_required": False,
                    "dependencies": {"nodejs": ">=20.0.0"},
                },
            }
        ],
    }

    import clawrium.core.install
    monkeypatch.setattr(clawrium.core.install, "load_manifest", lambda x: mock_manifest)

    # Create a mock SSH key
    key_file = tmp_path / "test_key"
    key_file.write_text("fake key")

    # Mock get_host
    compatible_host = {
        "hostname": "test-host",
        "user": "xclm",
        "port": 22,
        "key_id": "test-host",
        "hardware": {
            "architecture": "x86_64",
            "os": "ubuntu",
            "os_version": "24.04",
            "memtotal_mb": 4096,
        },
    }
    monkeypatch.setattr(clawrium.core.install, "get_host", lambda x: compatible_host)

    # Mock check_compatibility
    compat_result = {
        "compatible": True,
        "matched_entry": mock_manifest["entries"][0],
        "reasons": [],
    }
    monkeypatch.setattr(
        clawrium.core.install, "check_compatibility", lambda *args, **kwargs: compat_result
    )

    # Mock get_host_private_key
    monkeypatch.setattr(
        clawrium.core.install, "get_host_private_key", lambda x: key_file
    )

    # Mock ansible_runner.run
    class SuccessfulResult:
        status = "successful"

    mock_run = Mock(return_value=SuccessfulResult())

    import ansible_runner
    monkeypatch.setattr(ansible_runner, "run", mock_run)

    # Run installation
    result = run_installation("openclaw", "test-host")

    # Verify result
    assert result["success"] is True
    assert result["claw"] == "openclaw"
    assert result["version"] == "0.1.0"
    assert result["host"] == "test-host"
    assert len(result["playbooks_run"]) == 2
    assert result["error"] is None

    # Verify ansible_runner.run was called twice (base + claw playbook)
    assert mock_run.call_count == 2


def test_install_emits_events(monkeypatch, tmp_path):
    """Test that installation emits progress events."""
    from clawrium.core.install import run_installation

    # Mock dependencies (same as test_install_success)
    mock_manifest = {
        "name": "openclaw",
        "entries": [
            {
                "version": "0.1.0",
                "os": "ubuntu",
                "os_version": "24.04",
                "arch": "x86_64",
                "requirements": {
                    "min_memory_mb": 2048,
                    "gpu_required": False,
                    "dependencies": {"nodejs": ">=20.0.0"},
                },
            }
        ],
    }

    import clawrium.core.install
    monkeypatch.setattr(clawrium.core.install, "load_manifest", lambda x: mock_manifest)

    key_file = tmp_path / "test_key"
    key_file.write_text("fake key")

    compatible_host = {
        "hostname": "test-host",
        "user": "xclm",
        "port": 22,
        "key_id": "test-host",
        "hardware": {
            "architecture": "x86_64",
            "os": "ubuntu",
            "os_version": "24.04",
            "memtotal_mb": 4096,
        },
    }
    monkeypatch.setattr(clawrium.core.install, "get_host", lambda x: compatible_host)

    compat_result = {
        "compatible": True,
        "matched_entry": mock_manifest["entries"][0],
        "reasons": [],
    }
    monkeypatch.setattr(
        clawrium.core.install, "check_compatibility", lambda *args, **kwargs: compat_result
    )

    monkeypatch.setattr(
        clawrium.core.install, "get_host_private_key", lambda x: key_file
    )

    class SuccessfulResult:
        status = "successful"

    mock_run = Mock(return_value=SuccessfulResult())

    import ansible_runner
    monkeypatch.setattr(ansible_runner, "run", mock_run)

    # Capture events
    events = []

    def on_event(stage, message):
        events.append((stage, message))

    # Run installation with event callback
    run_installation("openclaw", "test-host", on_event=on_event)

    # Verify events were emitted
    assert len(events) > 0
    stages = [stage for stage, _ in events]
    assert "validate" in stages
    assert "base" in stages
    assert "claw" in stages


def test_install_base_playbook_fails(monkeypatch, tmp_path):
    """Test that base playbook failure raises InstallationError."""
    from clawrium.core.install import run_installation, InstallationError

    # Mock dependencies
    mock_manifest = {
        "name": "openclaw",
        "entries": [
            {
                "version": "0.1.0",
                "os": "ubuntu",
                "os_version": "24.04",
                "arch": "x86_64",
                "requirements": {
                    "min_memory_mb": 2048,
                    "gpu_required": False,
                    "dependencies": {"nodejs": ">=20.0.0"},
                },
            }
        ],
    }

    import clawrium.core.install
    monkeypatch.setattr(clawrium.core.install, "load_manifest", lambda x: mock_manifest)

    key_file = tmp_path / "test_key"
    key_file.write_text("fake key")

    compatible_host = {
        "hostname": "test-host",
        "user": "xclm",
        "port": 22,
        "key_id": "test-host",
        "hardware": {
            "architecture": "x86_64",
            "os": "ubuntu",
            "os_version": "24.04",
            "memtotal_mb": 4096,
        },
    }
    monkeypatch.setattr(clawrium.core.install, "get_host", lambda x: compatible_host)

    compat_result = {
        "compatible": True,
        "matched_entry": mock_manifest["entries"][0],
        "reasons": [],
    }
    monkeypatch.setattr(
        clawrium.core.install, "check_compatibility", lambda *args, **kwargs: compat_result
    )

    monkeypatch.setattr(
        clawrium.core.install, "get_host_private_key", lambda x: key_file
    )

    # Mock ansible_runner.run to fail
    class FailedResult:
        status = "failed"

    mock_run = Mock(return_value=FailedResult())

    import ansible_runner
    monkeypatch.setattr(ansible_runner, "run", mock_run)

    with pytest.raises(InstallationError, match="Base playbook failed"):
        run_installation("openclaw", "test-host")


def test_install_missing_ssh_key_raises(monkeypatch):
    """Test that missing SSH key raises InstallationError."""
    from clawrium.core.install import run_installation, InstallationError

    # Mock dependencies
    mock_manifest = {
        "name": "openclaw",
        "entries": [
            {
                "version": "0.1.0",
                "os": "ubuntu",
                "os_version": "24.04",
                "arch": "x86_64",
                "requirements": {
                    "min_memory_mb": 2048,
                    "gpu_required": False,
                    "dependencies": {"nodejs": ">=20.0.0"},
                },
            }
        ],
    }

    import clawrium.core.install
    monkeypatch.setattr(clawrium.core.install, "load_manifest", lambda x: mock_manifest)

    compatible_host = {
        "hostname": "test-host",
        "user": "xclm",
        "port": 22,
        "key_id": "test-host",
        "hardware": {
            "architecture": "x86_64",
            "os": "ubuntu",
            "os_version": "24.04",
            "memtotal_mb": 4096,
        },
    }
    monkeypatch.setattr(clawrium.core.install, "get_host", lambda x: compatible_host)

    compat_result = {
        "compatible": True,
        "matched_entry": mock_manifest["entries"][0],
        "reasons": [],
    }
    monkeypatch.setattr(
        clawrium.core.install, "check_compatibility", lambda *args, **kwargs: compat_result
    )

    # Mock get_host_private_key to return None
    monkeypatch.setattr(clawrium.core.install, "get_host_private_key", lambda x: None)

    with pytest.raises(InstallationError, match="No SSH key found"):
        run_installation("openclaw", "test-host")
