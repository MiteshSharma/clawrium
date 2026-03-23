---
phase: 06-make-secrets-specific-to-installed-claws-not-global
plan: 03
subsystem: health-status
tags: [health-check, status-display, secrets, degraded-state]
requirements: [PSEC-04]
dependency_graph:
  requires:
    - 06-01 (per-instance secret storage)
  provides:
    - degraded-state-detection
    - missing-secrets-display
  affects:
    - fleet-status-visibility
    - operational-awareness
tech_stack:
  added: []
  patterns:
    - health-check-with-secrets-validation
    - status-display-with-degraded-state
key_files:
  created: []
  modified:
    - src/clawrium/core/health.py
    - src/clawrium/cli/status.py
    - tests/test_health.py
    - tests/test_cli_status.py
decisions:
  - D-01: "DEGRADED status added to ClawStatus enum for running claws with missing required secrets"
  - D-02: "missing_secrets field added to HealthResult to track which keys are missing"
  - D-03: "get_missing_secrets() helper extracts claw name from user field (opc-work -> work)"
  - D-04: "Status display shows first 3 missing secrets, truncates rest with +N more"
  - D-05: "Degraded state displayed in yellow to indicate warning (not critical failure)"
metrics:
  duration: 336
  tasks_completed: 2
  files_modified: 4
  commits: 2
  completed_at: "2026-03-22T22:37:09Z"
---

# Phase 06 Plan 03: Degraded State for Missing Secrets Summary

**One-liner:** Fleet status now shows degraded state for running claws with missing required secrets, displaying which keys need to be set.

## What Was Built

Added degraded state detection and display to fleet health checks. Running claws with missing required secrets now show as "degraded (missing: KEY1, KEY2)" in yellow, allowing operators to see at a glance which claws need secret configuration.

### Core Implementation

**Health Module (`src/clawrium/core/health.py`):**
- Added `ClawStatus.DEGRADED` enum value for running claws with missing secrets
- Extended `HealthResult` TypedDict with `missing_secrets: list[str] | None` field
- Implemented `get_missing_secrets()` helper to check required secrets:
  - Extracts claw name from user field (e.g., "opc-work" -> "work")
  - Generates instance key using `get_instance_key(host, claw_type, claw_name)`
  - Fetches instance secrets via `get_instance_secrets(instance_key)`
  - Compares with `get_required_secrets(claw_type)` from manifest
  - Returns list of missing required secret keys
- Modified `check_claw_health()` to check secrets after process check:
  - If process RUNNING but missing required secrets → status = DEGRADED
  - If process RUNNING with all required secrets → status = RUNNING
  - Other statuses (STOPPED, UNKNOWN, etc.) → missing_secrets = None
- Updated all 8 return statements to include `missing_secrets` field

**Status CLI (`src/clawrium/cli/status.py`):**
- Changed `health_results` dict from `ClawStatus` to full `HealthResult` storage
- Added DEGRADED status display logic with yellow color:
  - Shows first 3 missing secret keys
  - Truncates remainder as "+N more" for long lists
  - Example: `degraded (missing: OPENAI_API_KEY, ANTHROPIC_API_KEY +1 more)`
- Updated status display to extract `status` and `missing_secrets` from result

### Testing

**Health Tests (`tests/test_health.py`):**
- `test_claw_status_degraded_exists` - DEGRADED enum value exists
- `test_health_result_has_missing_secrets_field` - HealthResult includes field
- `test_check_claw_health_degraded_when_missing_secrets` - All missing → DEGRADED
- `test_check_claw_health_running_when_all_secrets_present` - All present → RUNNING
- `test_check_claw_health_degraded_partial_secrets` - Some missing → DEGRADED with subset
- `test_missing_secrets_none_for_stopped_status` - STOPPED has None (not relevant)
- Updated existing tests to mock `get_required_secrets` for clean baselines

**Status CLI Tests (`tests/test_cli_status.py`):**
- `test_status_shows_degraded_with_missing_secrets` - Displays degraded with keys
- `test_status_degraded_truncates_long_list` - Truncates >3 keys with "+N more"
- Updated all existing tests to include `missing_secrets` field in mocks

All 29 tests pass (17 health + 12 status).

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash    | Type | Message                                            | Files |
|---------|------|----------------------------------------------------|-------|
| 5aabb31 | feat | Add DEGRADED status and missing_secrets to health  | 2     |
| 3cae1ab | feat | Display degraded state in fleet status             | 2     |

**Total:** 2 commits, 4 files modified, 0 files created.

## Verification

**Automated:**
```bash
uv run pytest tests/test_health.py tests/test_cli_status.py -v
# Result: 29 passed in 0.14s

uv run ruff check src/clawrium/core/health.py src/clawrium/cli/status.py
# Result: All checks passed!
```

**Manual (if testing locally):**
1. Install a claw on a host: `clm install openclaw <host>`
2. Check status without setting secrets: `clm status`
   - Should show: `degraded (missing: OPENAI_API_KEY)`
3. Set the required secret: `clm secret set <claw-name> OPENAI_API_KEY`
4. Check status again: `clm status`
   - Should show: `running` (green)

## Known Stubs

None. All functionality is fully wired:
- Health checks use live secret storage via `get_instance_secrets()`
- Required secrets come from manifest via `get_required_secrets()`
- Status display shows actual missing keys from health check results

## Integration Notes

**For operators:**
- `clm status` now shows which claws need secret configuration
- Yellow "degraded" means claw is running but won't work correctly without secrets
- Use `clm secret set <claw-name> <KEY>` to fix degraded claws

**For future plans:**
- Degraded state is distinct from STOPPED (process issue) and UNKNOWN (network issue)
- Health check now calls secrets module - depends on 06-01 instance key structure
- Plan 06-02 will add per-claw `secret set/list/remove` commands (currently uncommitted)

## Requirements Satisfied

- **PSEC-04:** Fleet status shows degraded state for claws with missing required secrets
  - Degraded message lists specific missing secret keys
  - Running claws with all secrets show as running, not degraded
  - Implemented via ClawStatus.DEGRADED enum and missing_secrets field

## Self-Check: PASSED

**Files created:** (none expected)

**Files modified:**
```bash
[ -f "src/clawrium/core/health.py" ] && echo "FOUND: src/clawrium/core/health.py" || echo "MISSING"
# FOUND: src/clawrium/core/health.py

[ -f "src/clawrium/cli/status.py" ] && echo "FOUND: src/clawrium/cli/status.py" || echo "MISSING"
# FOUND: src/clawrium/cli/status.py

[ -f "tests/test_health.py" ] && echo "FOUND: tests/test_health.py" || echo "MISSING"
# FOUND: tests/test_health.py

[ -f "tests/test_cli_status.py" ] && echo "FOUND: tests/test_cli_status.py" || echo "MISSING"
# FOUND: tests/test_cli_status.py
```

**Commits exist:**
```bash
git log --oneline --all | grep -q "5aabb31" && echo "FOUND: 5aabb31" || echo "MISSING"
# FOUND: 5aabb31

git log --oneline --all | grep -q "3cae1ab" && echo "FOUND: 3cae1ab" || echo "MISSING"
# FOUND: 3cae1ab
```

All files and commits verified.
