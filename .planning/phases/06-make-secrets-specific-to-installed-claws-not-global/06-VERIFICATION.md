---
phase: 06-make-secrets-specific-to-installed-claws-not-global
verified: 2026-03-22T22:42:18Z
status: passed
score: 12/12 must-haves verified
re_verification: false
---

# Phase 06: Per-Instance Secrets Verification Report

**Phase Goal:** Each installed claw has its own set of secrets; secrets are no longer global

**Verified:** 2026-03-22T22:42:18Z

**Status:** passed

**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Secrets are stored per claw instance, not globally | ✓ VERIFIED | `load_secrets()` returns `dict[str, dict[str, SecretEntry]]` with nested structure; tests verify multiple instances |
| 2 | Instance identity is host:claw_type:claw_name format | ✓ VERIFIED | `get_instance_key()` returns "host:claw_type:claw_name"; test_get_instance_key validates format |
| 3 | Same secret key can exist with different values per instance | ✓ VERIFIED | test_same_key_different_instances verifies same key with different values per instance |
| 4 | Secrets can only be set for installed claws | ✓ VERIFIED | `get_installed_claw()` validates claw exists in hosts registry; ClawNotFoundError raised if not found |
| 5 | User sets secrets with clm secret set <clawname> KEY | ✓ VERIFIED | CLI set_cmd signature requires claw_name as first argument; test_secret_set_with_claw validates |
| 6 | User lists secrets grouped by claw with missing required secrets | ✓ VERIFIED | CLI list_cmd shows secrets grouped by claw with host names; missing_keys displayed; test_secret_list_grouped_by_claw validates |
| 7 | Remove command requires claw name | ✓ VERIFIED | CLI remove_cmd signature requires claw_name as first argument; test_secret_remove_with_claw validates |
| 8 | Status shows degraded state for claws with missing required secrets | ✓ VERIFIED | ClawStatus.DEGRADED enum exists; check_claw_health returns DEGRADED when missing secrets; status display shows yellow degraded with keys |
| 9 | Degraded message lists specific missing secret keys | ✓ VERIFIED | HealthResult.missing_secrets populated with list; status.py displays first 3 keys with "+N more" truncation |
| 10 | Running claws with all secrets show as running, not degraded | ✓ VERIFIED | check_claw_health returns RUNNING when all required secrets present; test_check_claw_health_running_when_all_secrets_present validates |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| src/clawrium/core/secrets.py | Per-instance secret storage with nested JSON structure | ✓ VERIFIED | Exports: get_instance_key, get_installed_claw, get_instance_secrets, set_instance_secret, remove_instance_secret, list_instances_with_secrets, ClawNotFoundError; 525 lines; nested structure confirmed |
| tests/test_secrets.py | Tests for per-instance secret operations | ✓ VERIFIED | Contains: test_set_instance_secret, test_get_instance_key, test_same_key_different_instances, test_remove_instance_secret, test_list_instances_with_secrets; 421 lines |
| src/clawrium/cli/secret.py | CLI commands for per-claw secret management | ✓ VERIFIED | set_cmd, list_cmd, remove_cmd all require claw_name; uses set_instance_secret, get_instance_secrets; 218 lines |
| tests/test_cli_secret.py | Tests for per-claw CLI commands | ✓ VERIFIED | Contains: test_secret_set_with_claw, test_secret_set_claw_not_found, test_secret_list_grouped_by_claw, test_secret_remove_with_claw; imports and tests per-claw functions |
| src/clawrium/core/health.py | Health check with secrets validation | ✓ VERIFIED | Exports ClawStatus with DEGRADED; HealthResult includes missing_secrets field; get_missing_secrets() helper implemented; 269 lines |
| src/clawrium/cli/status.py | Fleet status with degraded state display | ✓ VERIFIED | Contains "degraded" string on line 117; displays missing secrets with truncation; uses HealthResult dict; 144 lines |
| tests/test_health.py | Tests for degraded state | ✓ VERIFIED | Contains: test_claw_status_degraded_exists, test_check_claw_health_degraded_when_missing_secrets, test_check_claw_health_running_when_all_secrets_present |
| tests/test_cli_status.py | Tests for degraded state display | ✓ VERIFIED | Contains: test_status_shows_degraded_with_missing_secrets, test_status_degraded_truncates_long_list |

**Artifacts:** 8/8 verified (all exist, substantive, wired)

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| src/clawrium/core/secrets.py | secrets.json | nested dict with instance keys | ✓ WIRED | load_secrets() returns nested structure; save_secrets() accepts nested dict; format: {instance_key: {secret_key: SecretEntry}} |
| src/clawrium/cli/secret.py | src/clawrium/core/secrets.py | set_instance_secret, get_instance_secrets | ✓ WIRED | Imports on lines 16-18; calls set_instance_secret on line 85; calls get_instance_secrets on lines 62, 200; get_installed_claw on lines 54, 192 |
| src/clawrium/cli/status.py | src/clawrium/core/secrets.py | get_instance_secrets for missing secrets check | ✓ WIRED | health.py imports get_instance_secrets on line 17; calls on line 63; status.py uses HealthResult which includes missing_secrets |
| src/clawrium/cli/status.py | src/clawrium/core/registry.py | get_required_secrets for manifest lookup | ✓ WIRED | health.py imports get_required_secrets on line 18; calls on line 65; compares required vs stored to determine missing |

**Key Links:** 4/4 verified (all wired)

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PSEC-01 | 06-01-PLAN | Secrets are scoped to installed claw instances, not global | ✓ SATISFIED | Nested JSON structure with instance keys; load_secrets() returns dict[str, dict[str, SecretEntry]]; test_same_key_different_instances validates |
| PSEC-02 | 06-02-PLAN | User sets secrets per claw (clm secret set <clawname> KEY) | ✓ SATISFIED | set_cmd signature requires claw_name as first positional argument; test_secret_set_with_claw validates workflow |
| PSEC-03 | 06-02-PLAN | User lists secrets grouped by claw with missing required secrets shown | ✓ SATISFIED | list_cmd iterates hosts/claws, displays per-instance tables with missing keys; test_secret_list_grouped_by_claw validates |
| PSEC-04 | 06-03-PLAN | Status shows degraded state for claws with missing required secrets | ✓ SATISFIED | ClawStatus.DEGRADED enum; get_missing_secrets() checks required vs stored; status displays yellow degraded with key names; test_check_claw_health_degraded validates |
| PSEC-05 | 06-01-PLAN | Secrets only settable for installed/initialized claws | ✓ SATISFIED | get_installed_claw() validates claw exists in hosts registry; raises ClawNotFoundError if not found; test_secret_set_claw_not_found validates error handling |

**Requirements:** 5/5 satisfied (all REQ IDs from plans accounted for and validated)

**Orphaned Requirements:** None (all requirements from ROADMAP Phase 6 mapped to plans)

### Anti-Patterns Found

None found.

**Scanned files:**
- src/clawrium/core/secrets.py — No TODOs, placeholders, or stub patterns
- src/clawrium/cli/secret.py — No TODOs, placeholders, or stub patterns
- src/clawrium/core/health.py — No TODOs, placeholders, or stub patterns
- src/clawrium/cli/status.py — No TODOs, placeholders, or stub patterns

**Stub check:** All functions return substantive values from actual data sources (load_secrets(), get_instance_secrets(), get_required_secrets()). No hardcoded empty arrays or null returns found outside of error paths.

### Human Verification Required

None. All functionality is programmatically verifiable and tested.

**Note:** While visual display (colors, table formatting) cannot be fully verified without running the CLI, the underlying data flow and logic have been validated through automated tests (273 tests pass).

## Verification Details

### Plan 06-01: Per-Instance Secret Storage

**Truths verified:**
1. ✓ Secrets are stored per claw instance, not globally — `load_secrets()` returns nested dict structure
2. ✓ Instance identity is host:claw_type:claw_name format — `get_instance_key()` implemented
3. ✓ Same secret key can exist with different values per instance — test_same_key_different_instances passes
4. ✓ Secrets can only be set for installed claws — `get_installed_claw()` validates against hosts registry

**Artifacts verified:**
- src/clawrium/core/secrets.py: 525 lines, exports 8 new functions, nested structure implemented
- tests/test_secrets.py: 421 lines, 19 tests for per-instance operations

**Key links verified:**
- secrets.json uses nested structure: {instance_key: {secret_key: SecretEntry}}
- Instance key format validated via test_get_instance_key
- File permissions preserved at 0o600 (test_file_permissions_per_instance)

**Commits verified:**
- 0979c64 — test(06-01): add failing tests for per-instance secrets
- 790040c — feat(06-01): implement per-instance secret storage

### Plan 06-02: CLI Per-Claw Commands

**Truths verified:**
1. ✓ User sets secrets with clm secret set <clawname> KEY — set_cmd signature verified
2. ✓ User lists secrets grouped by claw — list_cmd iterates hosts and displays per-claw tables
3. ✓ Secrets can only be set for installed claws — get_installed_claw() called in set_cmd and remove_cmd
4. ✓ Remove command requires claw name — remove_cmd signature verified

**Artifacts verified:**
- src/clawrium/cli/secret.py: 218 lines, all commands use per-instance functions
- tests/test_cli_secret.py: comprehensive tests for per-claw workflows

**Key links verified:**
- CLI imports: get_installed_claw, get_instance_key, get_instance_secrets, set_instance_secret, remove_instance_secret
- set_cmd calls get_installed_claw (line 54), set_instance_secret (line 85)
- list_cmd calls get_instance_secrets (line 134), get_required_secrets (line 137)
- remove_cmd calls get_installed_claw (line 192), remove_instance_secret (line 212)

**Commits verified:**
- e1690f2 — feat(06-02): update CLI set command for per-claw secrets
- d9f299b — feat(06-02): update CLI list and remove commands for per-claw secrets

### Plan 06-03: Degraded State Display

**Truths verified:**
1. ✓ Status shows degraded state for claws with missing required secrets — ClawStatus.DEGRADED implemented
2. ✓ Degraded message lists specific missing secret keys — HealthResult.missing_secrets populated and displayed
3. ✓ Running claws with all secrets show as running, not degraded — check_claw_health logic branches correctly

**Artifacts verified:**
- src/clawrium/core/health.py: 269 lines, DEGRADED status added, get_missing_secrets() implemented
- src/clawrium/cli/status.py: 144 lines, degraded display with truncation
- tests/test_health.py: 17 tests including degraded state tests
- tests/test_cli_status.py: 12 tests including degraded display tests

**Key links verified:**
- health.py imports get_instance_secrets (line 17), get_required_secrets (line 18)
- get_missing_secrets() calls both functions (lines 63, 65)
- check_claw_health() calls get_missing_secrets (line 210) and returns DEGRADED when missing
- status.py extracts missing_secrets from HealthResult (line 104) and displays (lines 111-119)

**Commits verified:**
- 5aabb31 — feat(06-03): add DEGRADED status and missing_secrets to health module
- 3cae1ab — feat(06-03): display degraded state in fleet status

### Test Suite Verification

**Test execution:**
```
make test
===== 273 passed in 2.94s =====
```

**Test coverage:**
- Per-instance secrets: 19 tests in test_secrets.py
- CLI per-claw commands: 22 tests in test_cli_secret.py
- Degraded state: 17 tests in test_health.py + 12 tests in test_cli_status.py

**Key test validations:**
- test_same_key_different_instances — validates same key with different values
- test_secret_set_with_claw — validates CLI per-claw set
- test_secret_list_grouped_by_claw — validates grouped display
- test_check_claw_health_degraded_when_missing_secrets — validates degraded detection
- test_status_shows_degraded_with_missing_secrets — validates degraded display

All tests pass with no failures or warnings.

## Success Criteria Verification

**From ROADMAP.md Phase 6:**

1. ✓ User runs `clm secret set <clawname> KEY` and secret is stored for that specific claw instance
   - **Evidence:** set_cmd requires claw_name, calls set_instance_secret with instance_key, test_secret_set_with_claw validates

2. ✓ User runs `clm secret list` and sees secrets grouped by claw with missing required secrets per claw
   - **Evidence:** list_cmd iterates hosts/claws, displays per-instance tables with missing keys, test_secret_list_grouped_by_claw validates

3. ✓ Same secret key can have different values per claw instance
   - **Evidence:** Nested storage structure {instance_key: {secret_key: SecretEntry}}, test_same_key_different_instances validates

4. ✓ Secrets can only be set for installed claws (validation enforced)
   - **Evidence:** get_installed_claw() validates against hosts registry, raises ClawNotFoundError, test_secret_set_claw_not_found validates

5. ✓ `clm status` shows degraded state for claws with missing required secrets
   - **Evidence:** ClawStatus.DEGRADED enum, check_claw_health returns DEGRADED when missing, status displays yellow "degraded (missing: KEY1, KEY2)", test_status_shows_degraded validates

**All 5 success criteria verified.**

## Summary

Phase 06 goal **ACHIEVED**. All must-haves verified:

- **Storage:** Per-instance secret storage with nested JSON structure implemented
- **Identity:** Instance key format "host:claw_type:claw_name" established
- **Isolation:** Same key can have different values per instance
- **Validation:** Secrets only settable for installed claws
- **CLI:** Commands require claw_name as first argument
- **Display:** List shows secrets grouped by claw with missing required secrets
- **Health:** Status shows degraded state with specific missing keys

**Quality indicators:**
- 273 tests pass (0 failures)
- No TODOs, placeholders, or stub patterns found
- All requirements satisfied (PSEC-01 through PSEC-05)
- All artifacts exist, substantive, and wired
- All key links verified
- 6 commits with descriptive messages
- Code follows TDD pattern (RED-GREEN cycle evident in commits)

Phase ready for next phase or release.

---

_Verified: 2026-03-22T22:42:18Z_

_Verifier: Claude (gsd-verifier)_
