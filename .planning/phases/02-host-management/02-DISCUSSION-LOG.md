# Phase 2: Host Management - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-21
**Phase:** 02-host-management
**Areas discussed:** Host storage format, SSH connection flow, Hardware detection, CLI command design

---

## Host Storage Format

| Option | Description | Selected |
|--------|-------------|----------|
| JSON (Recommended) | Native Python support, easy to read/edit, used by most tools in the ecosystem | ✓ |
| YAML | More human-readable, common in Ansible/DevOps, but requires pyyaml dependency | |
| TOML | Python-native (tomllib in 3.11+), clean syntax, good for config files | |

**User's choice:** JSON (Recommended)
**Notes:** No dependencies, native Python support

| Option | Description | Selected |
|--------|-------------|----------|
| Single hosts.json file | All hosts in one file, simple to manage, atomic updates, easy backup | ✓ |
| Directory per host | ~/.config/clawrium/hosts/<hostname>/, allows per-host files (keys, certs), more complexity | |

**User's choice:** Single hosts.json file

| Option | Description | Selected |
|--------|-------------|----------|
| User-provided alias (Recommended) | User names it (e.g., 'homelab', 'server01'), friendly, memorable | |
| Hostname/IP | Use the actual hostname or IP as identifier, less ambiguity but less friendly | ✓ |
| Auto-generated UUID | System-generated unique ID, works for any naming scheme, but harder to reference | |

**User's choice:** Hostname/IP
**Notes:** With optional alias for friendlier reference

| Option | Description | Selected |
|--------|-------------|----------|
| With hardware | Include hardware capabilities in the host record (detected on add, updated on status) | ✓ |
| With metadata | Include added_at timestamp, last_seen, tags for organization | ✓ |
| Minimal (Recommended) | hostname, port, user, auth_method, alias — only what's needed for connection | |

**User's choice:** With hardware, With metadata

| Option | Description | Selected |
|--------|-------------|----------|
| On add (Recommended) | Detect hardware when adding host — user immediately sees capabilities, slightly slower add | ✓ |
| On status only | Add is fast, hardware detected only when running 'clm host status' | |
| Both | Detect on add, refresh on status — best of both but more code | |

**User's choice:** On add (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Simple string tags | List of tags like ['homelab', 'gpu'], filterable in list command | ✓ |
| No tags for v1 | Skip tags, add later if needed | |

**User's choice:** Simple string tags

| Option | Description | Selected |
|--------|-------------|----------|
| Manual only | 'clm host status --refresh' to update hardware — explicit, predictable | ✓ |
| Auto on status | Always refresh hardware on 'clm host status' — slower but always fresh | |
| You decide | Claude picks the approach | |

**User's choice:** Manual only

---

## SSH Connection Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid | Flags for common cases, prompts fill in missing values | ✓ |
| Interactive prompts (Recommended) | Step-by-step prompts for hostname, port, user, auth — guided experience | |
| All via flags | 'clm host add --host x --port 22 --user y' — scriptable, but verbose | |

**User's choice:** Hybrid

| Option | Description | Selected |
|--------|-------------|----------|
| SSH key only (Recommended) | Default SSH agent or explicit key path — secure, no password storage | ✓ |
| SSH config integration | Honor ~/.ssh/config for hosts defined there — reuse existing setup | ✓ |
| Key + password | Support both key-based and password auth — more flexible, but password handling is tricky | |

**User's choice:** SSH key only + SSH config integration

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, test on add (Recommended) | Verify SSH connectivity before saving — catches typos early | ✓ |
| No, add without test | Save immediately, test later with 'clm host status' | |
| Optional --no-test flag | Test by default, skip with flag for special cases | |

**User's choice:** Yes, test on add (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Reject and don't save | Fail fast — host not added, user fixes issue and retries | ✓ |
| Warn but allow save | Show warning, offer to save anyway (useful for host that's temporarily down) | |
| Prompt for retry | Ask user: retry, save anyway, or cancel | |

**User's choice:** Reject and don't save

| Option | Description | Selected |
|--------|-------------|----------|
| Both | Auto-detect by default, --ssh-config flag to override or specify explicitly | ✓ |
| Auto-detect | If hostname matches an entry in ~/.ssh/config, use those settings automatically | |
| Explicit flag | 'clm host add --ssh-config myhost' to reference a specific ssh config entry | |

**User's choice:** Both

| Option | Description | Selected |
|--------|-------------|----------|
| Default to 22 (Recommended) | Standard port assumed, override with --port if different | ✓ |
| Always require | Force explicit port specification — more verbose but no assumptions | |

**User's choice:** Default to 22 (Recommended)

**SSH User Model (free-text input):**
User explained the two-user model:
- `xclm`: System admin user with root permissions for installation (pre-configured on all managed hosts)
- `<claw-prefix>-<hostname>`: Claw-specific user (e.g., `opc-kevin`) for claw operations, passwordless via authorized_keys

| Option | Description | Selected |
|--------|-------------|----------|
| xclm only for now | Store only xclm for Phase 2 — claw user handling comes with claw installation in Phase 5 | ✓ |
| Store both | Host record has system_user='xclm' and claw_user pattern — use appropriate one per operation | |

**User's choice:** xclm only for now

---

## Hardware Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Full set (Recommended) | Architecture, CPU cores, memory, disk space, GPU presence/type | ✓ |
| Minimal | Architecture only — minimum needed for compatibility checks | |
| Custom subset | Tell me which specific capabilities you want | |

**User's choice:** Full set (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Ansible facts | Use ansible gather_facts — richer data, but requires ansible-runner | ✓ |
| SSH commands (Recommended) | Run standard commands over SSH (uname, lscpu, free, df, lspci) — works on any Ubuntu | |
| You decide | Claude picks the approach | |

**User's choice:** Ansible facts

| Option | Description | Selected |
|--------|-------------|----------|
| Presence + vendor | Detect if GPU exists and vendor (NVIDIA, AMD, Intel) — enough for claw requirements | ✓ |
| Full GPU info | Vendor, model, VRAM, driver version — detailed but more complex | |
| Presence only | Just boolean 'has_gpu' — simplest | |

**User's choice:** Presence + vendor

**Hardware display:** User clarified hardware is for internal compatibility checking, not displayed to users.

---

## CLI Command Design

| Option | Description | Selected |
|--------|-------------|----------|
| clm host <action> (Recommended) | 'clm host add', 'clm host list', 'clm host remove', 'clm host status' | ✓ |
| clm <action>-host | 'clm add-host', 'clm list-hosts', 'clm remove-host' — flatter | |
| clm hosts + clm host | 'clm hosts' for list, 'clm host <name> status' for single host operations | |

**User's choice:** clm host <action> (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Rich table (Recommended) | Formatted table like init dependency display — consistent with Phase 1 | ✓ |
| Plain text | Simple lines, scriptable, no dependencies | |
| Both with --json | Table by default, --json flag for machine-readable output | |

**User's choice:** Rich table (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, interactive confirm | Prompt 'Remove host X? [y/N]' — safety first | ✓ |
| Yes, with --force flag | Confirm by default, --force skips — scriptable | |
| No confirmation | Remove immediately — user knows what they're doing | |

**User's choice:** Yes, interactive confirm

| Option | Description | Selected |
|--------|-------------|----------|
| Connection + service health | SSH reachable plus check if any claws are running (Phase 5 prep) | ✓ |
| Connection + basic info | SSH reachable, hostname verified, last seen timestamp | |
| Connection only | Just test SSH connectivity — simplest | |

**User's choice:** Connection + service health

---

## Claude's Discretion

- Exact schema field names and types
- Error message wording
- Table column layout and formatting
- Ansible playbook structure for hardware detection

## Deferred Ideas

- Claw user management — handled in Phase 5 with claw installation
- Password-based SSH authentication — security concern, key-only for v1
- GPU driver version detection — presence + vendor sufficient for compatibility
- Display hardware to users — not needed for v1, compatibility checking is internal
