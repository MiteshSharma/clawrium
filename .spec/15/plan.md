# Plan: Host Reset Command

> **Status**: ready
> **Issue**: #15
> **Spec**: [spec.md](./spec.md)
> **Created**: 2026-03-23
> **Author**: devashish (via claude-opus)

## Objective

Implement `clm host reset <host>` command that removes all users (uid >= 1000 except xclm), claw services, and config paths from a managed host via Ansible playbook.

## Prerequisites

- [x] Spec approved
- [x] Dependencies resolved (ansible-runner already in codebase)
- [x] Environment ready (`make test` passes)

## Tasks

### Task 1: Create test file for reset core module

**Files**: `tests/test_reset.py`

**Read First**:
- `tests/conftest.py` - understand fixtures (lines 1-173)
- `tests/test_install.py` - if exists, pattern for ansible mocking
- `src/clawrium/core/install.py` - pattern for InstallResult TypedDict (lines 54-62)

**Action**:
1. Create `tests/test_reset.py` with imports
2. Write test `test_reset_targets_dataclass_structure` - verify ResetTargets has users, services, paths fields
3. Write test `test_reset_result_dataclass_structure` - verify ResetResult has success, removed, errors fields
4. Write test `test_enumerate_targets_finds_users` - mock ansible to return users, verify filtering
5. Write test `test_enumerate_targets_excludes_xclm` - verify xclm is never in users list
6. Write test `test_enumerate_targets_finds_claw_services` - verify *claw*.service pattern matching
7. Write test `test_execute_reset_returns_result` - verify execute_reset returns ResetResult
8. Run tests (should fail - RED)

**Verification**:
```bash
uv run pytest tests/test_reset.py -v
# Expected: Tests fail with ImportError (no module yet)
```

**Acceptance**:
- [ ] `tests/test_reset.py` exists
- [ ] At least 7 test cases defined
- [ ] Tests fail with ImportError (not syntax error)

---

### Task 2: Create reset core module with dataclasses

**Files**: `src/clawrium/core/reset.py`

**Read First**:
- `src/clawrium/core/install.py` - pattern for TypedDict, ansible_runner usage (lines 1-100)
- `src/clawrium/core/hosts.py` - pattern for update_host (lines 117-156)

**Action**:
1. Create `src/clawrium/core/reset.py`
2. Add imports: dataclasses, logging, Path, datetime, ansible_runner
3. Define `ResetTargets` dataclass with: `users: list[str]`, `services: list[str]`, `paths: list[str]`
4. Define `ResetResult` dataclass with: `success: bool`, `removed: dict[str, int]`, `errors: list[str]`
5. Add `__all__` export list
6. Create stub `enumerate_targets(hostname: str) -> ResetTargets` that returns empty targets
7. Create stub `execute_reset(hostname: str, targets: ResetTargets) -> ResetResult` that returns success=False

**Verification**:
```bash
uv run pytest tests/test_reset.py -v
# Expected: Dataclass tests pass, logic tests fail
```

**Acceptance**:
- [ ] `src/clawrium/core/reset.py` exists
- [ ] Dataclass structure tests pass
- [ ] No lint errors: `uv run ruff check src/clawrium/core/reset.py`

---

### Task 3: Create reset playbook

**Files**: `src/clawrium/platform/playbooks/reset.yaml`

**Read First**:
- `src/clawrium/platform/playbooks/base.yaml` - ansible playbook pattern (lines 1-45)
- `.spec/15/spec.md` - playbook definition (lines 125-164)

**Action**:
1. Create `src/clawrium/platform/playbooks/reset.yaml`
2. Add YAML header with `hosts: all` and `become: yes`
3. Add task: Stop and disable claw services (loop over `services_to_remove`)
4. Add task: Remove service files from `/etc/systemd/system/`
5. Add task: Reload systemd daemon
6. Add task: Remove users and home directories (loop over `users_to_remove`, skip xclm)
7. Add task: Clean paths (loop over `paths_to_clean`)
8. Verify YAML syntax

**Verification**:
```bash
python3 -c "import yaml; yaml.safe_load(open('src/clawrium/platform/playbooks/reset.yaml'))"
# Expected: No errors
```

**Acceptance**:
- [ ] `src/clawrium/platform/playbooks/reset.yaml` exists
- [ ] Valid YAML (no syntax errors)
- [ ] Contains 5 tasks as specified

---

### Task 4: Implement enumerate_targets function

**Files**: `src/clawrium/core/reset.py`

**Read First**:
- `src/clawrium/core/hardware.py` - pattern for ansible_runner.run with inventory
- `src/clawrium/core/hosts.py` - get_host function (lines 244-259)
- `src/clawrium/core/keys.py` - get_host_private_key function

**Action**:
1. Add imports: `from clawrium.core.hosts import get_host` and `from clawrium.core.keys import get_host_private_key`
2. Implement `enumerate_targets`:
   - Get host record and SSH key
   - Build inventory dict with ansible_user, ansible_port, ansible_ssh_private_key_file
   - Run ansible ad-hoc command to get users: `getent passwd | awk -F: '$3 >= 1000 {print $1}'`
   - Filter out `xclm` from users list
   - Run ansible ad-hoc command to get services: `systemctl list-unit-files '*claw*.service' --no-legend | awk '{print $1}'`
   - Set paths to static list: `["/etc/clawrium/", "/var/log/clawrium/"]`
   - Return ResetTargets

**Verification**:
```bash
uv run pytest tests/test_reset.py::test_enumerate_targets_excludes_xclm -v
# Expected: Test passes (with mocked ansible)
```

**Acceptance**:
- [ ] `enumerate_targets` returns ResetTargets with filtered users
- [ ] xclm is never in users list
- [ ] Tests for enumerate pass

---

### Task 5: Implement execute_reset function

**Files**: `src/clawrium/core/reset.py`

**Read First**:
- `src/clawrium/core/install.py` - ansible_runner.run with playbook (lines 237-276)
- `src/clawrium/core/config.py` - get_config_dir for logs

**Action**:
1. Add imports: `from clawrium.core.config import get_config_dir`
2. Add helper `_get_reset_playbook_path() -> Path` returning playbook path
3. Add helper `_get_logs_dir() -> Path` for logs directory
4. Implement `execute_reset`:
   - Get host record and SSH key
   - Build inventory with extra vars: `services_to_remove`, `users_to_remove`, `paths_to_clean`
   - Create timestamped log directory: `logs/reset-<host>-<timestamp>/`
   - Run ansible_runner.run with reset playbook and 300s timeout
   - Parse result status and return ResetResult
   - Count removed items from ansible events

**Verification**:
```bash
uv run pytest tests/test_reset.py -v
# Expected: All tests pass
```

**Acceptance**:
- [ ] `execute_reset` returns ResetResult
- [ ] Logs created at expected path
- [ ] All core tests pass

---

### Task 6: Add tests for CLI reset command

**Files**: `tests/test_cli_host.py`

**Read First**:
- `tests/test_cli_host.py` - existing test patterns (lines 1-100)
- `.spec/15/spec.md` - CLI signature and behavior (lines 39-50)

**Action**:
1. Add test `test_host_reset_shows_in_help` - verify reset appears in `clm host --help`
2. Add test `test_host_reset_requires_host_arg` - verify error without hostname
3. Add test `test_host_reset_prompts_confirmation` - verify prompt when no --yes
4. Add test `test_host_reset_abort_on_no` - verify exit 0 when user says no
5. Add test `test_host_reset_dry_run_shows_targets` - verify --dry-run output format
6. Add test `test_host_reset_dry_run_changes_nothing` - verify no ansible called
7. Add test `test_host_reset_yes_skips_prompt` - verify --yes executes immediately
8. Add test `test_host_reset_updates_host_record` - verify claws: {} and last_reset
9. Add test `test_host_reset_untrack_removes_host` - verify --untrack removes from registry
10. Add test `test_host_reset_not_found` - verify error for unknown host
11. Run tests (should fail - RED)

**Verification**:
```bash
uv run pytest tests/test_cli_host.py::test_host_reset -v
# Expected: Tests fail (no reset command yet)
```

**Acceptance**:
- [ ] At least 10 new test cases for reset
- [ ] Tests fail with appropriate error (command not found)

---

### Task 7: Implement CLI reset command

**Files**: `src/clawrium/cli/host.py`

**Read First**:
- `src/clawrium/cli/host.py` - existing command patterns (lines 440-482 for remove)
- `.spec/15/spec.md` - CLI signature (lines 39-50)

**Action**:
1. Add imports: `from clawrium.core.reset import enumerate_targets, execute_reset, ResetTargets`
2. Add reset command with signature:
   ```python
   @host_app.command()
   def reset(
       hostname: str = typer.Argument(..., help="Host to reset"),
       yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
       dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be removed"),
       untrack: bool = typer.Option(False, "--untrack", help="Remove host from registry after reset"),
   ) -> None:
   ```
3. Implement flow:
   - Get host record, exit 1 if not found
   - Call enumerate_targets to get targets
   - Display targets in formatted output
   - If dry_run: print "[DRY RUN] Nothing changed." and exit 0
   - If not yes: prompt for confirmation, exit 0 if declined
   - Call execute_reset
   - If success: update host record (claws: {}, last_reset timestamp)
   - If untrack: call remove_host
   - Display result

**Verification**:
```bash
uv run pytest tests/test_cli_host.py::test_host_reset -v
# Expected: Most tests pass
```

**Acceptance**:
- [ ] `clm host reset` command exists
- [ ] --dry-run shows targets without changing
- [ ] --yes skips confirmation
- [ ] --untrack removes host from registry

---

### Task 8: Update host record after reset

**Files**: `src/clawrium/cli/host.py`, `src/clawrium/core/hosts.py`

**Read First**:
- `src/clawrium/core/hosts.py` - update_host function (lines 117-156)
- `.spec/15/spec.md` - expected host record state (line 189)

**Action**:
1. In `src/clawrium/cli/host.py` reset command, after successful execute_reset:
2. Create updater function that:
   - Sets `claws: {}` (empty dict)
   - Sets `metadata.last_reset` to current ISO timestamp
   - Preserves all other fields
3. Call `update_host(host["hostname"], updater)`
4. Add test for host record state after reset

**Verification**:
```bash
uv run pytest tests/test_cli_host.py::test_host_reset_updates_host_record -v
# Expected: Test passes
```

**Acceptance**:
- [ ] After reset, host record has `claws: {}`
- [ ] After reset, host record has `last_reset` timestamp
- [ ] Test verifies host record state

---

### Task 9: Integration and edge case tests

**Files**: `tests/test_reset.py`, `tests/test_cli_host.py`

**Read First**:
- `tests/test_cli_host.py` - mock patterns for SSH and ansible

**Action**:
1. Add test `test_reset_host_not_reachable` - verify graceful failure when SSH fails
2. Add test `test_reset_empty_targets` - verify behavior when nothing to remove
3. Add test `test_reset_partial_failure` - verify errors reported correctly
4. Add test `test_reset_logs_created` - verify logs at expected path
5. Add test `test_reset_preserves_xclm` - end-to-end verify xclm survives

**Verification**:
```bash
uv run pytest tests/test_reset.py tests/test_cli_host.py -v
# Expected: All tests pass
```

**Acceptance**:
- [ ] Edge cases covered
- [ ] Error handling tested
- [ ] Log creation verified

---

### Task 10: Final verification and cleanup

**Files**: All modified files

**Read First**:
- `.spec/15/spec.md` - acceptance criteria (lines 178-192)

**Action**:
1. Run full test suite: `make test`
2. Run linter: `make lint`
3. Fix any lint errors
4. Verify all acceptance criteria from spec:
   - [ ] `clm host --help` shows `reset` command
   - [ ] `clm host reset myhost` prompts for confirmation
   - [ ] `clm host reset myhost --dry-run` shows targets
   - [ ] `clm host reset myhost --yes` executes without prompt
   - [ ] After reset: no users with uid >= 1000 except xclm
   - [ ] After reset: no `*claw*.service` in systemd
   - [ ] After reset: config paths don't exist
   - [ ] After reset: host record has `claws: {}` and `last_reset`
   - [ ] `--untrack` removes host from registry
   - [ ] Logs at expected path

**Verification**:
```bash
make test && make lint
# Expected: All pass, no lint errors
```

**Acceptance**:
- [ ] All tests pass
- [ ] No lint errors
- [ ] All spec acceptance criteria met

---

## Final Verification

```bash
# Run full verification
make test && make lint
```

## Success Criteria

All acceptance criteria from spec.md are met:
- [ ] `clm host --help` shows `reset` command
- [ ] `clm host reset myhost` prompts for confirmation, exits 0 on abort
- [ ] `clm host reset myhost --dry-run` shows targets, changes nothing
- [ ] `clm host reset myhost --yes` executes without prompt
- [ ] After reset: no users with uid >= 1000 except xclm
- [ ] After reset: no `*claw*.service` in systemd
- [ ] After reset: `/etc/clawrium/` and `/var/log/clawrium/` don't exist
- [ ] After reset: host record has `claws: {}` and `last_reset` timestamp
- [ ] `--untrack` removes host from local registry
- [ ] Logs at `~/.config/clawrium/logs/reset-<host>-<timestamp>/`
- [ ] `make test` passes

---

<details>
<summary>Prompt Log</summary>

```yaml
- model: anthropic.claude-opus-4-5-20251101-v1:0
  date: 2026-03-23
  type: plan-creation
  prompt: |
    Create execution plan for issue 15 (Host Reset Command).
    Read spec.md, analyze codebase patterns in src/clawrium/ and tests/,
    create detailed tasks following TDD approach (tests first).
    Each task should be 15-30 minutes, independently verifiable,
    with exact files, read-first context, numbered actions,
    verification commands, and acceptance criteria.
```

</details>
