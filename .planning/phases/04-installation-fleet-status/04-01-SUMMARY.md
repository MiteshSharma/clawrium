---
phase: 04-installation-fleet-status
plan: 01
subsystem: installation
tags: [ansible, playbooks, orchestration, tdd]
dependency_graph:
  requires: [registry-compatibility, host-management, ssh-keys]
  provides: [installation-playbooks, installation-orchestration]
  affects: [cli-install-command]
tech_stack:
  added: [ansible-playbooks]
  patterns: [tdd-red-green-refactor, event-streaming]
key_files:
  created:
    - platform/playbooks/base.yaml
    - src/clawrium/platform/registry/openclaw/playbooks/install.yaml
    - src/clawrium/core/install.py
    - tests/test_playbooks.py
    - tests/test_install.py
  modified: []
decisions:
  - "Base playbook located at project root (platform/) not in src/ for easier discovery"
  - "Ansible playbooks use become:yes - assumes xclm user has passwordless sudo per D-08"
  - "OpenClaw user naming pattern: opc-<hostname> using inventory_hostname variable"
  - "Event streaming via optional callback for progress tracking in CLI"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_created: 5
  test_coverage: 11
  commits: 2
  completed: 2026-03-22
---

# Phase 04 Plan 01: Installation Infrastructure Summary

**One-liner:** Created Ansible playbooks for base system setup and OpenClaw installation, plus Python orchestration module with compatibility validation and event streaming

## What Was Built

### Task 1: Ansible Playbooks
Created two idempotent playbooks following Ansible best practices:

**Base playbook** (`platform/playbooks/base.yaml`):
- Updates apt cache with validity check
- Installs NodeSource GPG key and Node.js 20 repository
- Installs nodejs package
- Installs build-essential for native module compilation
- All tasks use `become: yes` (assumes xclm has passwordless sudo)

**OpenClaw install playbook** (`src/clawrium/platform/registry/openclaw/playbooks/install.yaml`):
- Creates claw user `opc-{{ inventory_hostname }}` with home directory
- Clones OpenClaw repository from GitHub
- Runs npm install as claw user
- Creates workspace directory with correct permissions
- Uses `inventory_hostname` variable for per-host user naming (D-07)

### Task 2: Installation Orchestration
Created `install.py` core module with full validation and error handling:

**Validation flow:**
1. Load claw manifest (validates claw exists)
2. Get host record (validates host exists)
3. Check compatibility (validates hardware requirements)
4. Get SSH key (validates credentials available)

**Execution flow:**
1. Build Ansible inventory with SSH credentials
2. Run base playbook (system dependencies)
3. Run claw-specific playbook (application installation)
4. Return structured result with playbooks executed

**Error handling:**
- `InstallationError` with clear messages for all failure modes
- Compatibility reasons included in error messages
- Playbook failure status captured and reported

**Event streaming:**
- Optional `on_event(stage, message)` callback for progress tracking
- Stages: validate, base, claw
- Ready for CLI integration with live progress display

## Tests Written

**test_playbooks.py** (4 tests):
- Verifies both playbooks exist and are valid YAML
- Checks for required elements (hosts, become, nodejs, opc-, etc.)

**test_install.py** (7 tests):
- Invalid claw raises InstallationError
- Host not found raises InstallationError
- Incompatible host raises InstallationError with reasons
- Successful installation returns correct result
- Event callback receives progress updates
- Base playbook failure raises InstallationError
- Missing SSH key raises InstallationError

All tests use mocking patterns from existing hardware.py tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed base playbook path calculation**
- **Found during:** Task 2 testing (GREEN phase)
- **Issue:** `_get_base_playbook_path()` calculated wrong path (src/platform/ instead of platform/)
- **Fix:** Changed from `parent.parent.parent` to `parent.parent.parent.parent` to reach project root
- **Files modified:** src/clawrium/core/install.py
- **Commit:** ec2cd9f (part of Task 2)
- **Reason:** Bug - tests failed because playbook path was incorrect

No other deviations - plan executed exactly as written.

## Key Decisions

1. **Base playbook location:** Placed at project root `platform/playbooks/` instead of `src/clawrium/platform/playbooks/` for easier discovery and separation of concerns (playbooks are deployment artifacts, not Python code)

2. **Sudo assumption:** Playbooks use `become: yes` without password prompts, following Decision D-08 that xclm user has passwordless sudo configured during host setup

3. **Claw user naming:** Using `opc-{{ inventory_hostname }}` pattern ensures unique users per host per claw type, following Decision D-07

4. **Event streaming design:** Optional callback pattern allows CLI to display live progress while keeping core module decoupled from UI concerns

## Integration Points

**Ready for CLI integration** (Plan 02):
- `run_installation(claw_name, hostname, on_event)` provides complete installation flow
- Returns structured `InstallResult` with success status, version, playbooks run
- Raises `InstallationError` with user-friendly messages for all failure modes

**Depends on:**
- `clawrium.core.registry.check_compatibility()` - Phase 03
- `clawrium.core.hosts.get_host()` - Phase 02
- `clawrium.core.keys.get_host_private_key()` - Phase 02

**Provides for:**
- Phase 04 Plan 02: CLI install command implementation
- Phase 04 Plan 03: Fleet status tracking (installed claw versions)

## Verification

### Must-Have Truths
- ✅ Compatibility is validated before any installation starts
- ✅ Installation fails with clear error if host is incompatible
- ✅ Base playbook installs system dependencies without claw-specific code
- ✅ OpenClaw playbook installs claw-specific components

### Artifacts Verified
- ✅ `platform/playbooks/base.yaml` exists with "- hosts:" and nodejs tasks
- ✅ `src/clawrium/platform/registry/openclaw/playbooks/install.yaml` exists with opc- user and npm install
- ✅ `src/clawrium/core/install.py` exports `run_installation` and `InstallationError`
- ✅ Tests cover both success and failure paths
- ✅ All 11 tests passing (4 playbook + 7 install)

### Key Links Verified
- ✅ install.py imports `check_compatibility` from registry.py
- ✅ install.py uses `ansible_runner.run` for playbook execution
- ✅ Playbooks use correct variable references (inventory_hostname)

## Self-Check: PASSED

**Files created:**
- ✅ platform/playbooks/base.yaml exists
- ✅ src/clawrium/platform/registry/openclaw/playbooks/install.yaml exists
- ✅ src/clawrium/core/install.py exists
- ✅ tests/test_playbooks.py exists
- ✅ tests/test_install.py exists

**Commits verified:**
- ✅ d3cd802: feat(04-01): create base and openclaw installation playbooks
- ✅ ec2cd9f: feat(04-01): create installation orchestration module

**Tests verified:**
```bash
make test
# 166 passed in 2.45s
```

All claims verified. Plan execution successful.

## Known Stubs

None - all functionality is fully implemented and wired. No placeholder data or hardcoded stubs.

## Next Steps

Plan 02 will create the CLI `install` command that:
1. Parses user input (claw name, host identifier)
2. Calls `run_installation()` with event callback for progress display
3. Displays results in user-friendly format
4. Handles errors gracefully with actionable messages

The infrastructure is ready for integration.
