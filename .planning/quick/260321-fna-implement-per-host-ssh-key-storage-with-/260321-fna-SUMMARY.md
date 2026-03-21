---
phase: quick
plan: 260321-fna
subsystem: host-management
tags: [ssh, keys, security, cli]
dependency_graph:
  requires: [core-config, ssh-connection]
  provides: [per-host-keys, host-init-command]
  affects: [host-add, host-remove, host-status]
tech_stack:
  added: [cryptography]
  patterns: [per-host-isolation, init-first-workflow]
key_files:
  created:
    - src/clawrium/core/keys.py
    - tests/test_keys.py
    - docs/host-preparation.md
    - docs/index.md
  modified:
    - src/clawrium/cli/host.py
    - tests/test_cli_host.py
decisions:
  - "Per-host keypairs in keys/<hostname>/ for isolation"
  - "Init-first workflow: keypair must exist before host add"
  - "Host remove also deletes per-host keys"
metrics:
  duration: 7m
  completed: 2026-03-21T18:28:17Z
---

# Quick Task 260321-fna: Per-Host SSH Key Storage Summary

Per-host SSH keypair storage with `clm host init` command for automated xclm user setup.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create keys module with per-host storage | 38e3307 | keys.py, test_keys.py |
| 2 | Implement clm host init command | 1c9b7c6 | host.py, test_cli_host.py |
| 3 | Update host add/remove and docs | f1fc1fc | host.py, docs/*.md |

## Implementation Details

### Keys Module (src/clawrium/core/keys.py)

New module for per-host SSH key management:

- `get_host_key_dir(hostname)` - Returns `~/.config/clawrium/keys/<hostname>/`
- `get_host_private_key(hostname)` - Returns path to `xclm_ed25519` or None
- `get_host_public_key(hostname)` - Returns path to `xclm_ed25519.pub` or None
- `generate_host_keypair(hostname)` - Creates ed25519 keypair with 0600/0700 permissions
- `delete_host_keys(hostname)` - Removes entire key directory
- `read_public_key(hostname)` - Returns public key content

Uses `cryptography` library (already available via paramiko dependency).

### Host Init Command

New `clm host init <hostname> --user <ssh-user>` command:

1. **Generates per-host keypair** (if not exists)
2. **Attempts auto-setup** via SSH connection:
   - Creates xclm user
   - Configures passwordless sudo
   - Copies public key to authorized_keys
   - Verifies xclm access works
3. **Falls back to manual instructions** if SSH connection fails:
   - Displays setup commands
   - Shows public key for copy-paste

### Updated Commands

**host add:**
- Now requires keypair to exist (enforces init-first workflow)
- Uses per-host key instead of SSH config identityfile
- Removed --key option (no longer needed)

**host remove:**
- Deletes per-host keys on successful removal
- Shows confirmation message for key deletion

**host status:**
- Uses per-host key for connection testing

## Deviations from Plan

None - plan executed exactly as written.

## Test Coverage

- 16 tests for keys module (all functions)
- 4 new tests for host init command
- 2 new tests for updated host add/remove behavior
- Total: 102 tests passing

## Self-Check: PASSED

**Created files exist:**
- FOUND: /home/devashish/workspace/ric03uec/clawrium/src/clawrium/core/keys.py
- FOUND: /home/devashish/workspace/ric03uec/clawrium/tests/test_keys.py
- FOUND: /home/devashish/workspace/ric03uec/clawrium/docs/host-preparation.md
- FOUND: /home/devashish/workspace/ric03uec/clawrium/docs/index.md

**Commits exist:**
- FOUND: 38e3307
- FOUND: 1c9b7c6
- FOUND: f1fc1fc
