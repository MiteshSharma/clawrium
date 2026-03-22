# Phase 6: Make Secrets Specific to Installed Claws - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-22
**Phase:** 06-make-secrets-specific-to-installed-claws-not-global
**Areas discussed:** Scoping model, Storage structure, CLI command changes, Install flow changes

---

## Scoping Model

| Option | Description | Selected |
|--------|-------------|----------|
| Per claw instance | Each installed claw has its own secrets. Most flexible. | ✓ |
| Per host | All claws on a host share secrets. | |
| Per claw type | All openclaw instances share secrets. | |

**User's choice:** Per claw instance
**Notes:** Most flexible approach, allows different API keys per claw even on same host.

---

| Option | Description | Selected |
|--------|-------------|----------|
| host:claw-type | Simple. Assumes max 1 claw per type per host. | |
| host:claw-type:name | Allows multiple claws of same type per host. | ✓ |
| Unique instance UUID | Auto-generated UUID. Opaque to users. | |

**User's choice:** host:claw-type:name
**Notes:** All three components always present during install.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both, deprecate global | Global secrets still work with warning. | |
| Auto-migrate to instances | One-time migration. | |
| Break clean, remove global | Users re-set secrets per instance. | ✓ |

**User's choice:** Break clean, remove global
**Notes:** Simpler code, clean separation from Phase 5.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, per-instance values | Same key can have different values per instance. | ✓ |
| No, keys are global | Key names unique system-wide. | |

**User's choice:** Yes, per-instance values
**Notes:** OPENAI_API_KEY can differ between wolf:openclaw:work and wolf:openclaw:personal.

---

| Option | Description | Selected |
|--------|-------------|----------|
| No templates | Each instance sets secrets from scratch. | ✓ |
| Claw-type templates | Default secrets per claw type. | |
| Copy from instance | Duplicate secrets from another instance. | |

**User's choice:** No templates
**Notes:** Users can script if they want bulk setup.

---

## Storage Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Nested JSON | Single secrets.json with instance keys. | ✓ |
| Separate files per instance | One file per instance. | |
| SQLite | Better querying but adds dependency. | |

**User's choice:** Nested JSON
**Notes:** Reuses existing file locking pattern.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Colon-separated | 'wolf:openclaw:work' as top-level key. | ✓ |
| Tuple structure | Nested: { 'wolf': { 'openclaw': { 'work': {...} } } } | |
| UUID as key | Instance UUID from install record. | |

**User's choice:** Colon-separated
**Notes:** Matches CLI identifier format.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Clean break | New format only. Breaking change. | ✓ |
| Version field | Handle both formats for backward compatibility. | |

**User's choice:** Clean break
**Notes:** Simpler code.

---

## CLI Command Changes

| Option | Description | Selected |
|--------|-------------|----------|
| clm secret set <clawname> KEY | Claw name first, then key name. | ✓ |
| Flag-based | Key first, --instance flag for claw. | |
| Interactive selection | Prompt with list of installed claws. | |

**User's choice:** Positional with clawname first
**Notes:** User confirmed format. Secrets only work after claw is initialized.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Per-claw grouping | Shows all claws, their secrets, and missing required secrets. | ✓ |
| Require claw argument | Shows secrets for one claw only. | |
| Both modes | Both global list and filtered view. | |

**User's choice:** Per-claw grouping
**Notes:** Comprehensive view of fleet secrets status.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Claw name only | Simple if claw names are unique across hosts. | ✓ |
| Full instance path | Explicit but verbose. | |
| Partial match with prompt | Matches, prompts if ambiguous. | |

**User's choice:** Claw name only
**Notes:** Assumes uniqueness across hosts.

---

## Install Flow Changes

| Option | Description | Selected |
|--------|-------------|----------|
| Post-install required | Install succeeds without secrets. Set later. | ✓ |
| During install prompt | Prompts for required secrets before finishing. | |
| Optional during install | Prompts 'Set secrets now? [y/N]'. | |

**User's choice:** Post-install required
**Notes:** Clear separation of concerns.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Degraded state | Claw shows as 'degraded' with missing secrets message. | ✓ |
| Not ready indicator | Less detail about why. | |
| Separate secrets column | '2/3 set' or '✗ incomplete'. | |

**User's choice:** Degraded state
**Notes:** Clear indication of what's missing.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Manual resync | User runs 'clm install --sync' to apply new secrets. | ✓ |
| Auto-restart on change | Immediate but disruptive. | |
| No auto-sync | Secrets only applied on next install/upgrade. | |

**User's choice:** Manual resync
**Notes:** User controls when claw restarts.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Manifest validation at install | Fails fast if manifest is malformed. | ✓ |
| Validation only at secret set | User discovers issues at set time. | |
| Registry validation | Early catch but separate step. | |

**User's choice:** Manifest validation at install
**Notes:** Fail fast approach.

---

| Option | Description | Selected |
|--------|-------------|----------|
| New 'clm claw sync' | Dedicated command. | |
| Reuse 'clm install --sync' | Add --sync flag. Less new code. | ✓ |
| Defer sync command | Phase 7. | |

**User's choice:** Reuse 'clm install --sync'
**Notes:** Reuses playbooks, less new code.

---

## Claude's Discretion

- Exact JSON schema field names and nesting structure
- Error messages and help text wording
- Internal function signatures and module organization
- Test fixture structure

## Deferred Ideas

- Encryption at rest — adds key management complexity, defer to v2
- `clm claw sync` as dedicated command — using `clm install --sync` for now
- Secret templates or copy-from — users can script if needed
- Auto-restart on secret change — manual sync for v1
