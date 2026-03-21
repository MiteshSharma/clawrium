# Phase 2: Host Management - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Add, list, remove hosts with automatic hardware capability detection. Users can manage their host fleet with SSH-based connectivity and store hardware capabilities for future compatibility checking. This phase establishes the host infrastructure that claw installation (Phase 5) will build upon.

</domain>

<decisions>
## Implementation Decisions

### Host Storage Format
- **D-01:** JSON format for hosts file (native Python support, no dependencies)
- **D-02:** Single `hosts.json` file in `~/.config/clawrium/` (not directory-per-host)
- **D-03:** Hostname/IP as primary identifier, with optional friendly alias
- **D-04:** Schema includes: hostname, port, user, auth_method, alias, hardware capabilities, metadata (added_at, last_seen, tags)
- **D-05:** Simple string tags supported for host organization
- **D-06:** Hardware detected on add, refreshed only via explicit `clm host status --refresh`

### SSH Connection Flow
- **D-07:** Hybrid input: flags for common cases, prompts fill missing values
- **D-08:** SSH key only authentication (no password support) via SSH agent or explicit key path
- **D-09:** Honor ~/.ssh/config — auto-detect matching entries, allow explicit --ssh-config flag
- **D-10:** Test connection on add — reject and don't save if connection fails
- **D-11:** Default port 22, default user `xclm` (system admin user for installations)
- **D-12:** Two-user model: `xclm` for system ops (stored now), claw users (`<prefix>-<hostname>`) for claw ops (Phase 5)

### Hardware Detection
- **D-13:** Full capability set: architecture, CPU cores, memory, disk space, GPU (presence + vendor)
- **D-14:** Use Ansible facts via ansible-runner for hardware detection
- **D-15:** Hardware stored for compatibility checking (Phase 3), not displayed to users by default

### CLI Command Design
- **D-16:** Subcommand structure: `clm host add`, `clm host list`, `clm host remove`, `clm host status`
- **D-17:** Rich table output for `clm host list` (consistent with Phase 1 dependency display)
- **D-18:** Interactive confirmation for `clm host remove`
- **D-19:** `clm host status` shows: connection status, hostname verified, last seen, service health (prep for claw status in Phase 5)

### Claude's Discretion
- Exact schema field names and types
- Error message wording
- Table column layout and formatting
- Ansible playbook structure for hardware detection

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — HOST-01 through HOST-05 specifications

### Existing Code
- `src/clawrium/core/config.py` — Config directory management to extend for hosts.json
- `src/clawrium/cli/init.py` — Rich table output pattern to reuse

### Project Constraints
- `.planning/PROJECT.md` — Tech stack (Typer, ansible-runner), no-sudo policy, Ubuntu only

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/config.py`: `get_config_dir()` and `init_config_dir()` for config directory path
- `cli/init.py`: Rich console and table patterns for CLI output
- Rich library already imported and used

### Established Patterns
- Typer for CLI with callback pattern
- Rich tables for structured output
- Core module for business logic, CLI module for commands

### Integration Points
- New `cli/host.py` command module, registered in `cli/main.py`
- New `core/hosts.py` for host storage and management
- New `core/hardware.py` for ansible-runner hardware detection

</code_context>

<specifics>
## Specific Ideas

- All managed hosts have `xclm` user with root permissions (pre-configured on machines)
- Claw-specific users follow pattern `<claw-prefix>-<hostname>` (e.g., `opc-kevin`)
- SSH authorized keys set up for passwordless access from control host
- Hardware capabilities used for claw compatibility (Phase 3), not displayed unless explicitly requested

</specifics>

<deferred>
## Deferred Ideas

- Claw user management — handled in Phase 5 with claw installation
- Password-based SSH authentication — security concern, key-only for v1
- GPU driver version detection — presence + vendor sufficient for compatibility
- Display hardware to users — not needed for v1, compatibility checking is internal

</deferred>

---

*Phase: 02-host-management*
*Context gathered: 2026-03-21*
