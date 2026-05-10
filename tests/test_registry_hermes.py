"""Tests for the hermes agent type registration in the bundled registry."""

from clawrium.core.registry import (
    check_compatibility,
    get_claw_info,
    list_claws,
    load_manifest,
)


def test_hermes_listed_in_registry():
    """list_claws() should include 'hermes' alongside openclaw and zeroclaw."""
    claws = list_claws()
    assert "hermes" in claws


def test_hermes_manifest_validates():
    """load_manifest('hermes') parses and returns a typed manifest."""
    manifest = load_manifest("hermes")

    assert manifest["agent"]["type"] == "hermes"
    assert manifest["agent"]["description"]
    assert manifest["platforms"]
    # Provider keys are optional in Phase 1; required is empty.
    secrets = manifest.get("secrets", {})
    assert secrets.get("required", []) == []
    optional_keys = [s["key"] for s in secrets.get("optional", [])]
    assert "OPENROUTER_API_KEY" in optional_keys
    assert "ANTHROPIC_API_KEY" in optional_keys
    assert "OPENAI_API_KEY" in optional_keys


def test_hermes_manifest_has_installer_checksum():
    """Every platform entry must declare a non-empty sha256 for installer pinning."""
    manifest = load_manifest("hermes")

    assert len(manifest["platforms"]) >= 1
    for entry in manifest["platforms"]:
        sha256 = entry.get("sha256")
        assert isinstance(sha256, str), (
            f"Platform entry missing sha256: {entry.get('os')} {entry.get('os_version')}"
        )
        assert len(sha256) == 64, (
            f"sha256 should be 64 hex chars, got {len(sha256)}: {sha256!r}"
        )


def test_hermes_manifest_declares_memory_workspace():
    """Phase 3 prerequisite: workspace.memory_path and features.memory must be set."""
    manifest = load_manifest("hermes")

    workspace = manifest.get("workspace", {})
    assert workspace.get("memory_path") == "~/.hermes/memories"

    features = manifest.get("features", {})
    assert features.get("memory") is True


def test_hermes_get_claw_info():
    """get_claw_info('hermes') returns a sane summary."""
    info = get_claw_info("hermes")

    assert info["agent_type"] == "hermes"
    assert info["latest_version"]
    assert any("ubuntu 24.04 x86_64" == p for p in info["supported_platforms"])


def test_hermes_compatibility_ubuntu_2404_x86_64():
    """A vanilla Ubuntu 24.04 x86_64 host with enough RAM should be compatible."""
    hardware = {
        "os": "ubuntu",
        "os_version": "24.04",
        "architecture": "x86_64",
        "memtotal_mb": 8192,
        "gpu": {"present": False, "vendor": None, "error": None},
        "processor_cores": 8,
        "processor_count": 1,
        "mounts": [],
    }

    result = check_compatibility("hermes", hardware)

    assert result["compatible"] is True
    assert result["matched_entry"] is not None
    assert result["matched_entry"]["os"] == "ubuntu"
    assert result["matched_entry"]["arch"] == "x86_64"


def test_hermes_compatibility_insufficient_memory():
    """A host below min_memory_mb should be reported as incompatible."""
    hardware = {
        "os": "ubuntu",
        "os_version": "24.04",
        "architecture": "x86_64",
        "memtotal_mb": 1024,  # below 2048 min
        "gpu": {"present": False, "vendor": None, "error": None},
        "processor_cores": 4,
        "processor_count": 1,
        "mounts": [],
    }

    result = check_compatibility("hermes", hardware)
    assert result["compatible"] is False
    assert any(
        "memory" in reason.lower() or "ram" in reason.lower()
        for reason in result["reasons"]
    )


def test_hermes_install_playbook_shape():
    """The hermes install playbook must encode the documented invocation."""
    from importlib.resources import files
    import yaml

    hermes_pkg = files("clawrium.platform.registry.hermes")
    playbook_path = hermes_pkg / "playbooks" / "install.yaml"

    content = playbook_path.read_text()

    # Required structural elements.
    assert "- hosts:" in content
    assert "agent_name" in content
    # Hermes-specific install command flags.
    assert "--skip-setup" in content
    assert "--branch" in content
    assert "--hermes-home" in content
    assert "/home/{{ agent_name }}/.hermes" in content
    assert "/home/{{ agent_name }}/.local/bin/hermes" in content
    # Preflight checks reference the canonical binary names. We use `which`
    # (executable in /usr/bin) rather than the shell builtin `command -v`,
    # since ansible.builtin.command does not invoke a shell.
    assert "which rg" in content
    assert "which ffmpeg" in content
    # Service unit MUST NOT be enabled or started in install.yaml.
    assert "ExecStart=/home/{{ agent_name }}/.local/bin/hermes gateway start" in content
    assert "EnvironmentFile=/home/{{ agent_name }}/.hermes/.env" in content

    data = yaml.safe_load(content)
    tasks = data[0]["tasks"]
    enable_tasks = [
        t
        for t in tasks
        if t.get("ansible.builtin.systemd", {}).get("enabled") is True
        or t.get("ansible.builtin.systemd", {}).get("state") == "started"
    ]
    assert enable_tasks == [], (
        "install.yaml must not enable or start the hermes service; that is Phase 2's job"
    )


def test_hermes_remove_playbook_cleans_user_and_dirs():
    """remove.yaml must remove the unit, ~/.hermes/, the bin symlink, and the user."""
    from importlib.resources import files

    hermes_pkg = files("clawrium.platform.registry.hermes")
    remove_path = hermes_pkg / "playbooks" / "remove.yaml"
    content = remove_path.read_text()

    assert "/etc/systemd/system/{{ agent_type }}-{{ agent_name }}.service" in content
    assert "/home/{{ agent_name }}/.hermes" in content
    assert "/home/{{ agent_name }}/.local/bin/hermes" in content
    assert "remove: yes" in content
    # Hermes enables linger for its agent user; userdel fails without
    # disable-linger + pkill first.
    assert "loginctl disable-linger" in content
    assert "pkill" in content


def test_hermes_install_force_drops_binary_before_reinstall():
    """install.yaml must remove the binary when force_install=true so the
    `creates:` short-circuit on the runtime install task does not block reinstall."""
    from importlib.resources import files
    import yaml

    hermes_pkg = files("clawrium.platform.registry.hermes")
    install_path = hermes_pkg / "playbooks" / "install.yaml"
    content = install_path.read_text()
    data = yaml.safe_load(content)
    tasks = data[0]["tasks"]

    matching = [
        t
        for t in tasks
        if "Remove existing Hermes binary" in t.get("name", "")
    ]
    assert matching, (
        "install.yaml must remove the existing hermes binary when --force is set"
    )
    task = matching[0]
    when = task.get("when", [])
    assert any("force_install" in w for w in when), (
        "binary-removal task must be gated on force_install"
    )
    assert (
        task["ansible.builtin.file"]["path"]
        == "/home/{{ agent_name }}/.local/bin/hermes"
    )
    assert task["ansible.builtin.file"]["state"] == "absent"


def test_hermes_install_env_file_permissions_enforced():
    """install.yaml must enforce 0600 on ~/.hermes/.env, since the upstream
    installer creates it with 0644 and we'll write provider keys there in Phase 2."""
    from importlib.resources import files
    import yaml

    hermes_pkg = files("clawrium.platform.registry.hermes")
    install_path = hermes_pkg / "playbooks" / "install.yaml"
    data = yaml.safe_load(install_path.read_text())
    tasks = data[0]["tasks"]

    enforce = [
        t for t in tasks if "Enforce 0600" in t.get("name", "")
    ]
    assert enforce, "install.yaml must enforce 0600 on ~/.hermes/.env"
    file_args = enforce[0]["ansible.builtin.file"]
    assert file_args["path"] == "/home/{{ agent_name }}/.hermes/.env"
    assert file_args["mode"] == "0600"
