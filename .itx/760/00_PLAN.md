# Issue #760 — Sync agent workspace from control plane to data plane

Add a per-agent `workspace/` slot under the local control-plane config
directory and mirror it onto the agent host on every `clawctl agent sync`.
The destination is the upstream-canonical operator-overlay zone for each
agent type, taken straight from upstream docs.

This iteration ships Ubuntu (Linux x86_64) only. macOS support is split
into three follow-up subtasks tracked separately.

## 1. User-Centric Outputs

### New control-plane convention

A `workspace/` subdirectory inside each agent's local config dir is
operator-droppable. Anything the operator places under it is mirrored
onto the agent host on every `clawctl agent sync` (and `configure`).

```
~/.config/clawrium/agents/<type>/<name>/workspace/   ← drop files here
```

Whatever relative path the operator uses inside `workspace/` is the
same relative path the file lands at under the per-type destination
root on the host.

### Destination roots (Ubuntu, this iteration)

Sourced from upstream docs — see the "Verified from upstream" section
at the bottom of this plan for citations.

| Agent type | Host destination root | Exclude list |
|---|---|---|
| **openclaw** | `/home/<name>/.openclaw/workspace/` | none — disjoint from canonical render |
| **zeroclaw** | `/home/<name>/.zeroclaw/workspace/` | none — operator override of `force: no` seed is intended |
| **hermes** | `/home/<name>/.hermes/` (profile root) | `config.yaml`, `.env`, `auth.json` |

Why hermes has an exclude list: hermes' upstream layout has no sibling
`workspace/` dir; `~/.hermes/` is both the canonical-render zone and
the operator-overlay zone. Without the exclude, a stale local
`workspace/.env` could clobber the freshly rendered secrets file, which
is exactly the silent-wipe regression class issue #555 forbade. The
exclude list is hard-coded per agent type — operators cannot override.

### CLI surface

Existing `clawctl agent sync <name>` behavior:

- Default sync now also pushes the workspace overlay after the
  canonical write phase, before the restart phase.
- New `--workspace-only` flag pushes the workspace and nothing else:
  no canonical render, no secret-removal guard, no restart, no health
  verify. Useful for staging a workspace change without flapping the
  agent unit.
- Existing `--workspace` flag (which today means "skip restart") is
  unchanged. The two flags are distinct.

```bash
# Default sync — canonical render + workspace overlay + restart
clawctl agent sync ws-hermes

# Workspace overlay only — no render, no restart
clawctl agent sync ws-hermes --workspace-only

# Existing flag, unchanged — canonical render + workspace overlay, no restart
clawctl agent sync ws-hermes --workspace
```

### Example sessions

```bash
# Stage a profile override for hermes
$ mkdir -p ~/.config/clawrium/agents/hermes/ws-hermes/workspace/profiles/coder
$ cat > ~/.config/clawrium/agents/hermes/ws-hermes/workspace/profiles/coder/SOUL.md <<EOF
You are a senior staff engineer focused on Python.
EOF
$ clawctl agent sync ws-hermes
agent/ws-hermes  validating local state ...
agent/ws-hermes  validating local state
agent/ws-hermes  pushing config (provider, skills, channels, env) ...
agent/ws-hermes  pushing config (provider, skills, channels, env)
agent/ws-hermes  pushing workspace overlay ...
agent/ws-hermes  pushing workspace overlay (1 file)
agent/ws-hermes  restarting unit ...
agent/ws-hermes  restarting unit
agent/ws-hermes  verifying health ...
agent/ws-hermes  verifying health
agent/ws-hermes  synced  (drift=0, took 4s, 0 written, 2 unchanged, 1 workspace)

# Verify it landed
$ clawctl agent shell ws-hermes -- 'cat ~/.hermes/profiles/coder/SOUL.md'
You are a senior staff engineer focused on Python.

# Try to slip a hostile config.yaml — must be silently excluded
$ echo "model: { provider: evil }" > ~/.config/clawrium/agents/hermes/ws-hermes/workspace/config.yaml
$ clawctl agent sync ws-hermes -o json
{"resource":"agent/ws-hermes","phase":"workspace","state":"excluded","path":"config.yaml","reason":"hermes canonical-managed"}
{"resource":"agent/ws-hermes","phase":"workspace","state":"complete","files_pushed":["profiles/coder/SOUL.md"]}
...
$ clawctl agent shell ws-hermes -- 'grep provider ~/.hermes/config.yaml'
  provider: "openrouter"      # canonical-render value, hostile file rejected
```

## 2. Files to Modify

| Path | Change |
|---|---|
| `src/clawrium/core/workspace_sync.py` | **NEW**. Per-type destination map + exclude map; `enumerate_workspace_files`; `push_workspace_files`; Linux-only `NotImplementedError` for `os_family != "linux"`. |
| `src/clawrium/core/lifecycle_canonical.py` | New `workspace` phase between the canonical `write` loop and `restart`. New `push_workspace: bool = True` flag on `sync_agent_canonical`. New `workspace_files_pushed: tuple[str, ...]` field on `CanonicalSyncResult`. |
| `src/clawrium/cli/clawctl/agent/sync.py` | Add `--workspace-only` flag with mutual-exclusion checks against `--dry-run --diff`. Extend NDJSON `complete` payload. New phase line "pushing workspace overlay". |
| `src/clawrium/cli/clawctl/agent/configure.py` | Mirror workspace push in first-time `configure_agent`. |
| `src/clawrium/core/install.py` | On `clawctl agent create`, `mkdir -p` `~/.config/clawrium/agents/<type>/<name>/workspace/` for all three agent types. |
| `tests/unit/core/test_workspace_sync.py` | **NEW**. Unit tests — see §3. |
| `tests/integration/test_workspace_overlay_ubuntu.py` | **NEW**. Mocked-SSH integration tests — see §3. |
| `CHANGELOG.md` `[Unreleased]` | `### Added` entry. |
| `docs/operations/sync.md` (+ website mirror) | Document the overlay model, per-type destinations, exclude list, `--workspace-only`. |
| `AGENTS.md` | "Workspace Overlay" section pinning the destination + exclude table. |

## 3. Test Plan

### 3.1 Unit tests (`tests/unit/core/test_workspace_sync.py`)

| # | Test | What it asserts |
|---|---|---|
| U1 | `test_destination_map_covers_every_registry_type` | Every agent type loaded from `platform/registry/` has an entry in `_DESTINATION_BY_TYPE`. Hard-fails on a new agent type that forgets to declare a destination. |
| U2 | `test_destination_map_values_match_upstream` | Pin the literals: `openclaw → ~/.openclaw/workspace`, `zeroclaw → ~/.zeroclaw/workspace`, `hermes → ~/.hermes`. A future ATX iteration that "fixes" a path silently can't pass. |
| U3 | `test_hermes_excludes_canonical_managed_files` | `_WORKSPACE_EXCLUDES_BY_TYPE["hermes"]` contains exactly `{"config.yaml", ".env", "auth.json"}`. |
| U4 | `test_openclaw_zeroclaw_have_no_excludes` | The two non-hermes entries are empty frozensets. |
| U5 | `test_renderer_output_vs_exclude_invariant` | For every agent type, the set of rendered file paths (`render_<type>(inputs).files.keys()`) that would land under the destination root must be a subset of the exclude list. Catches the "new template file silently shadowed by workspace push" regression class. |
| U6 | `test_enumerate_skips_symlinks` | A symlink inside the local workspace is not enumerated; a `WorkspaceSkipped` event is emitted with reason `symlink`. |
| U7 | `test_enumerate_skips_dotfiles_with_clawrium_prefix` | Files matching `.clawrium-*` are skipped (reserved for future control-plane state). |
| U8 | `test_enumerate_rejects_path_traversal` | A workspace containing a file whose resolved path escapes the workspace root raises `WorkspaceSyncError`. |
| U9 | `test_enumerate_preserves_relative_path_structure` | A file at `workspace/profiles/coder/SOUL.md` enumerates to relative path `profiles/coder/SOUL.md`. |
| U10 | `test_push_preserves_local_mode_bits` | Local file mode 0644 / 0600 / 0755 round-trip to identical mode on remote (mocked SFTP + `sudo install`). |
| U11 | `test_push_chowns_to_agent_user` | Mocked `sudo install` is called with `-o <agent_name> -g <agent_name>`. |
| U12 | `test_push_mkdir_p_with_correct_ownership` | Intermediate dirs (`profiles/coder/`) are created with mode 0700, owner `<agent_name>`. |
| U13 | `test_linux_only_gate_raises_on_darwin` | Calling `push_workspace_files` with `os_family="darwin"` raises `NotImplementedError` with a message referencing the macOS follow-up subtasks. |
| U14 | `test_empty_workspace_is_noop` | An empty local `workspace/` dir results in zero SFTP calls, zero `sudo install` calls, and an empty `files_pushed` list. |
| U15 | `test_missing_workspace_dir_is_noop` | A local `workspace/` dir that does not exist is treated as empty, not an error. |
| U16 | `test_hermes_excluded_files_emit_excluded_events` | When `config.yaml` is present in a hermes local workspace, the enumeration emits a `WorkspaceExcluded` event with `path="config.yaml"` and `reason="hermes canonical-managed"`. Operator sees what was skipped. |

### 3.2 Integration tests (`tests/integration/test_workspace_overlay_ubuntu.py`)

All integration tests use the existing paramiko-mock fixture (same
shape as `test_render_matrix.py` integration suite). They assert the
full sync pipeline emits the right phase events and writes the right
files to the mocked remote.

| # | Test | What it asserts |
|---|---|---|
| I1 | `test_sync_pushes_openclaw_workspace_to_canonical_dir` | Stage `workspace/IDENTITY.md` locally; run `sync_agent_canonical`; assert mocked SFTP wrote to `/home/<name>/.openclaw/workspace/IDENTITY.md` and that `_atomic_write` was called with the right mode/owner. |
| I2 | `test_sync_pushes_zeroclaw_workspace_overlay_wins_over_seed` | Stage `workspace/SOUL.md` locally with custom content; canonical render seeds the workspace with default `SOUL.md`; the sync ordering pushes canonical FIRST, workspace SECOND — assert the operator's `SOUL.md` is the final write on the mocked remote (operator-wins). |
| I3 | `test_sync_pushes_hermes_workspace_skipping_excludes` | Stage `workspace/profiles/coder/SOUL.md` AND a hostile `workspace/config.yaml` AND a hostile `workspace/.env`; run sync; assert SFTP wrote `profiles/coder/SOUL.md` only and that `config.yaml`+`.env` triggered `WorkspaceExcluded` events. |
| I4 | `test_workspace_only_flag_skips_canonical_render` | Run with `--workspace-only`; assert the canonical renderer was NEVER called, the secret-removal guard was NEVER invoked, and the systemd restart was NEVER triggered. Only SFTP+install for the workspace files. |
| I5 | `test_workspace_only_with_empty_workspace_emits_nothing_pushed` | `--workspace-only` against an empty workspace exits 0 with `files_pushed=[]`. No-op safe. |
| I6 | `test_dry_run_skips_workspace_push` | `--dry-run` reports the workspace files that WOULD be pushed without actually invoking SFTP. NDJSON includes a `workspace` phase event with `state="skipped (dry-run)"`. |
| I7 | `test_workspace_only_and_diff_are_mutually_exclusive` | `clawctl agent sync ws-hermes --workspace-only --diff` exits 2 with a clear error pointing the operator to the two non-overlapping flag groups. |
| I8 | `test_workspace_failure_does_not_corrupt_canonical_state` | Mocked SFTP raises mid-push on file 3 of 5; assert the canonical files written earlier in the pipeline are still on the mocked remote, the systemd unit was NOT restarted (we abort the phase before restart), and `CanonicalSyncResult.success=False` with `error` referencing the workspace phase. |
| I9 | `test_workspace_push_emits_per_file_ndjson` | `-o json` mode emits one NDJSON line per workspace file pushed, with fields `{path, remote_path, mode, owner}`. Log-aggregator friendly. |
| I10 | `test_macos_host_emits_skipped_event_not_error` | A host record with `os_family="darwin"` does NOT raise; the workspace phase emits `state="skipped (os_family=darwin)"` and the sync completes successfully through the rest of the pipeline. macOS is deferred, not broken. |

### 3.3 End-to-end verification on `wolf-i` (Linux x86_64)

This is the manual + scripted verification that locks the feature
against the real host before merge. **Use the existing `wolf-i`
host** (Linux x86_64, hostname `wolf.tailf7742d.ts.net`) — three
fresh agents provisioned from scratch, distinct names so they don't
collide with the existing `wolf-i` openclaw agent.

Agent test names:

- `ws-hermes` (type: hermes)
- `ws-zeroclaw` (type: zeroclaw)
- `ws-openclaw` (type: openclaw)

#### 3.3.1 Provisioning sequence (run once per agent type)

For each agent type, the verifier runs the full ground-up provisioning
flow so the test covers `install → configure → sync` rather than only
the post-install sync path. The provider+channel attachments below are
the same ones the existing `wolf-i` agent uses (`clawrium-gtm-litellm`
provider + `discord-wolf-i` channel), so no new control-plane records
need to be created.

```bash
# 1. Agent registration — creates ~/.config/clawrium/agents/<type>/<name>/workspace/
clawctl agent create ws-openclaw  --type openclaw  --host wolf-i
clawctl agent create ws-zeroclaw  --type zeroclaw  --host wolf-i
clawctl agent create ws-hermes    --type hermes    --host wolf-i

# Assert the workspace dir scaffold exists locally
test -d ~/.config/clawrium/agents/openclaw/ws-openclaw/workspace
test -d ~/.config/clawrium/agents/zeroclaw/ws-zeroclaw/workspace
test -d ~/.config/clawrium/agents/hermes/ws-hermes/workspace

# 2. Attach provider + channel for each
for a in ws-openclaw ws-zeroclaw ws-hermes; do
  clawctl agent provider attach $a --provider clawrium-gtm-litellm
  clawctl agent channel  attach $a --channel  discord-wolf-i || true   # discord only if supported
done

# 3. Install binaries + systemd units on wolf-i
clawctl agent install ws-openclaw
clawctl agent install ws-zeroclaw
clawctl agent install ws-hermes

# 4. Configure — runs the canonical render + first restart
clawctl agent configure ws-openclaw
clawctl agent configure ws-zeroclaw
clawctl agent configure ws-hermes

# 5. Baseline sanity — every agent must be active on wolf-i before workspace tests
clawctl agent doctor ws-openclaw
clawctl agent doctor ws-zeroclaw
clawctl agent doctor ws-hermes
```

If any of the above fails the workspace E2E is blocked — file a
provisioning bug separate from #760.

#### 3.3.2 Workspace overlay verification

For each provisioned agent, run the same scripted matrix:

**E1 — openclaw (`ws-openclaw`) — `/home/ws-openclaw/.openclaw/workspace/`**

```bash
# Stage operator file
echo "Test marker $(date -u +%FT%TZ)" \
  > ~/.config/clawrium/agents/openclaw/ws-openclaw/workspace/MARKER.md

# Sync
clawctl agent sync ws-openclaw -o json | tee /tmp/ws-openclaw-sync.ndjson

# Verify file landed
clawctl agent shell ws-openclaw -- 'cat ~/.openclaw/workspace/MARKER.md'

# Verify mode + owner
clawctl agent shell ws-openclaw -- 'stat -c "%a %U:%G" ~/.openclaw/workspace/MARKER.md'
# Expect: 0644 ws-openclaw:ws-openclaw  (mode preserved, ownership = agent user)

# Verify the systemd unit was restarted exactly once (and the agent is still active)
clawctl agent doctor ws-openclaw
```

**E2 — zeroclaw (`ws-zeroclaw`) — `/home/ws-zeroclaw/.zeroclaw/workspace/` — operator-overrides-seed test**

```bash
# Read what canonical render seeded
clawctl agent shell ws-zeroclaw -- 'cat ~/.zeroclaw/workspace/SOUL.md' \
  > /tmp/zc-soul-canonical.txt

# Stage an operator override
cat > ~/.config/clawrium/agents/zeroclaw/ws-zeroclaw/workspace/SOUL.md <<EOF
# Operator-Overridden Personality
You are a terse Rust expert. No fluff.
EOF

# Sync
clawctl agent sync ws-zeroclaw

# Verify operator wins
clawctl agent shell ws-zeroclaw -- 'cat ~/.zeroclaw/workspace/SOUL.md' \
  > /tmp/zc-soul-after-sync.txt
grep "terse Rust expert" /tmp/zc-soul-after-sync.txt

# Verify bearer re-pair still ran (AGENTS.md "Gateway Token Lifecycle" requirement)
grep 'gateway_token_rotated' /tmp/ws-zeroclaw-sync.ndjson || \
  clawctl agent sync ws-zeroclaw -o json | grep gateway_token_rotated

# Confirm agent is still active
clawctl agent doctor ws-zeroclaw
```

**E3 — hermes (`ws-hermes`) — `/home/ws-hermes/.hermes/` with exclude list enforced**

```bash
# Stage a valid profile override
mkdir -p ~/.config/clawrium/agents/hermes/ws-hermes/workspace/profiles/coder
echo "You are a senior staff engineer focused on Python." \
  > ~/.config/clawrium/agents/hermes/ws-hermes/workspace/profiles/coder/SOUL.md

# Stage a memory file
echo "Project: workspace overlay E2E test on wolf-i" \
  > ~/.config/clawrium/agents/hermes/ws-hermes/workspace/memories/NOTES.md

# Stage hostile files that MUST be excluded
cat > ~/.config/clawrium/agents/hermes/ws-hermes/workspace/config.yaml <<EOF
model:
  provider: "evil"
EOF
echo "OPENROUTER_API_KEY=fake-key" \
  > ~/.config/clawrium/agents/hermes/ws-hermes/workspace/.env
echo '{"oauth":"fake"}' \
  > ~/.config/clawrium/agents/hermes/ws-hermes/workspace/auth.json

# Capture pre-sync values of the canonical-managed files
clawctl agent shell ws-hermes -- 'cat ~/.hermes/config.yaml' > /tmp/hermes-config-pre.yaml
clawctl agent shell ws-hermes -- 'cat ~/.hermes/.env'        > /tmp/hermes-env-pre

# Sync
clawctl agent sync ws-hermes -o json | tee /tmp/ws-hermes-sync.ndjson

# Verify good files landed
clawctl agent shell ws-hermes -- 'cat ~/.hermes/profiles/coder/SOUL.md' \
  | grep "senior staff engineer"
clawctl agent shell ws-hermes -- 'cat ~/.hermes/memories/NOTES.md' \
  | grep "wolf-i"

# Verify hostile files were REJECTED
clawctl agent shell ws-hermes -- 'cat ~/.hermes/config.yaml' > /tmp/hermes-config-post.yaml
clawctl agent shell ws-hermes -- 'cat ~/.hermes/.env'        > /tmp/hermes-env-post
diff /tmp/hermes-config-pre.yaml /tmp/hermes-config-post.yaml   # must be empty
diff /tmp/hermes-env-pre /tmp/hermes-env-post                   # must be empty

# Verify the operator saw the excluded events in NDJSON
grep '"state":"excluded"'      /tmp/ws-hermes-sync.ndjson | grep -F config.yaml
grep '"state":"excluded"'      /tmp/ws-hermes-sync.ndjson | grep -F .env
grep '"state":"excluded"'      /tmp/ws-hermes-sync.ndjson | grep -F auth.json

# Confirm agent is still active
clawctl agent doctor ws-hermes
```

#### 3.3.3 `--workspace-only` verification

For each of the three provisioned agents:

```bash
# Modify workspace file
date -u +%FT%TZ \
  >> ~/.config/clawrium/agents/openclaw/ws-openclaw/workspace/MARKER.md

# Capture unit start time pre-sync
start_pre=$(clawctl agent shell ws-openclaw -- \
  'systemctl show openclaw-ws-openclaw.service --property=ActiveEnterTimestamp --value')

# Workspace-only sync
clawctl agent sync ws-openclaw --workspace-only

# Capture unit start time post-sync — must be identical (no restart)
start_post=$(clawctl agent shell ws-openclaw -- \
  'systemctl show openclaw-ws-openclaw.service --property=ActiveEnterTimestamp --value')
test "$start_pre" = "$start_post"

# Verify file was still pushed
clawctl agent shell ws-openclaw -- 'tail -1 ~/.openclaw/workspace/MARKER.md'
```

#### 3.3.4 Cleanup

```bash
clawctl agent remove ws-openclaw  --yes
clawctl agent remove ws-zeroclaw  --yes
clawctl agent remove ws-hermes    --yes
```

The existing `wolf-i` openclaw agent (currently in `failed` state per
the upgrade-strips-attachments bug) is untouched by this E2E.

### 3.4 Definition of done

Code is mergeable when:

1. All §3.1 unit tests pass (`make test`).
2. All §3.2 integration tests pass.
3. All §3.3 E2E steps complete successfully on wolf-i.
4. `make lint` is clean.
5. `CHANGELOG.md` carries the `### Added` entry under `[Unreleased]`.
6. `docs/operations/sync.md` and its website mirror document the new
   behavior. The website mirror is verbatim-equal to the engineering
   doc body per the CLAUDE.md mirror rule.
7. `AGENTS.md` carries the Workspace Overlay section pinning the
   destination + exclude table.
8. ATX review (`mcp.review_enabled = true` per `.claude/itx-config.json`)
   has rated the PR > 3/5 with all `B#` blockers resolved.

## 4. Subtasks

The 3 agents × 2 OSes verification matrix becomes six subtasks. The
three Ubuntu cells are the in-scope work for this iteration; the
three macOS cells are tracked as follow-ups so they don't block the
Ubuntu ship.

### In scope (Ubuntu, this iteration)

1. **`[Parent #760] Ubuntu: verify openclaw workspace overlay → /home/<name>/.openclaw/workspace/`**
   - Implements §3.3 step E1 against wolf-i.
2. **`[Parent #760] Ubuntu: verify zeroclaw workspace overlay → /home/<name>/.zeroclaw/workspace/`**
   - Implements §3.3 step E2 (operator-overrides-seed) against wolf-i.
3. **`[Parent #760] Ubuntu: verify hermes workspace overlay → /home/<name>/.hermes/ with exclude list`**
   - Implements §3.3 step E3 (hostile-file exclude enforcement) against wolf-i.

### Deferred (macOS, follow-up)

4. **`[Parent #760] macOS: extend openclaw workspace overlay → /Users/<name>/.openclaw/workspace/`**
   - Lifts the `os_family=="darwin"` `NotImplementedError`; verifies against `mac-test`.
5. **`[Parent #760] macOS: extend zeroclaw workspace overlay → /Users/<name>/.zeroclaw/workspace/`**
   - Same shape as #4 for zeroclaw.
6. **`[Parent #760] macOS: extend hermes workspace overlay → /Users/<name>/.hermes/`**
   - Same shape as #4 for hermes; exclude list reused.

## 5. Risks

- **Hermes exclude-list drift.** If a future hermes canonical template
  renders a new file (upstream rename `auth.json` → `credentials.json`,
  say) the exclude list must extend. Mitigated by U5
  (renderer-output-vs-exclude invariant) — the test hard-fails until
  the exclude list is updated.
- **Operator surprise on silent exclude.** Operator might not notice
  their hostile `config.yaml` was dropped. Mitigated by emitting per-file
  `WorkspaceExcluded` NDJSON events plus a yellow notice in text mode
  ("excluded N files: see --output json for details").
- **Symlink trust.** SFTP can follow symlinks server-side in unexpected
  ways. Mitigated by enumerating only regular files on the control plane
  and refusing to follow symlinks, plus a per-file path-traversal check.
- **Mode preservation across SFTP.** paramiko's SFTP `put` does NOT
  preserve mode by default; we explicitly chmod after `install`. U10
  pins this.
- **No delete-on-host.** Issue mandates additive sync. A file the
  operator deletes locally stays on host until they `clawctl agent
  shell ... -- rm`. Documented explicitly in `docs/operations/sync.md`.

## 6. Verified from upstream

### Hermes (`https://hermes-agent.nousresearch.com/docs`)

- `~/.hermes/` layout: `config.yaml`, `.env`, `auth.json`, `SOUL.md`,
  `memories/`, `skills/`, `cron/`, `sessions/`, `logs/`, `profiles/<name>/`.
- Hermes uses a **profile** model, NOT a workspace model. Profiles are
  full subtrees under `~/.hermes/profiles/<name>/` (or `~/.hermes/` for
  the default profile), scoped via the `HERMES_HOME` env var.
- No `~/.hermes/workspace/` directory exists in upstream hermes.
- `config.yaml` top-level keys per upstream: `model`, `agent`,
  `terminal`, `compression`, `memory`, `display`, `skills`, `tts`,
  `stt`, `voice`, `web`, `browser`, `auxiliary`, `updates`, `streaming`,
  `quick_commands`.

### OpenClaw (`https://docs.openclaw.ai/concepts/agent-workspace`)

- Upstream explicitly separates config zone (`~/.openclaw/`) from
  workspace zone (`~/.openclaw/workspace/`).
- Workspace zone is explicitly designed as the operator-customizable
  overlay slot — upstream recommends backing it up in a private git
  repo.
- Standard workspace files: `AGENTS.md`, `SOUL.md`, `USER.md`,
  `IDENTITY.md`, `TOOLS.md`, `HEARTBEAT.md`, `STARTUP.md`, `BOOT.md`,
  `ONBOARD.md`, `memory/`, `skills/`, `canvas/`.
- Workspace path is configurable via `agents.defaults.workspace` in
  `openclaw.json`; default is `~/.openclaw/workspace/` or
  `~/.openclaw/workspace-<profile>/` if a profile is set.

### ZeroClaw (`https://docs.zeroclawlabs.ai/master/en/`)

- `~/.zeroclaw/workspace/` holds personality MD files (`SOUL.md`,
  `IDENTITY.md`, `USER.md`, `AGENTS.md`, `TOOLS.md`, `MEMORY.md`,
  `HEARTBEAT.md`, `BOOTSTRAP.md`), `skills/`, `memory/`, `state/`.
- Same operator-overlay design as openclaw — files are the operator's
  to edit; clawctl seeds them with `force: no` so re-render never
  clobbers operator edits.

## Prompt Log

**Stage**: planning
**Skill**: /itx:plan-create
**Timestamp**: 2026-06-20T00:00:00Z
**Model**: claude-opus-4-7

```prompt
760 plan only. no file creation
```

Followed by clarifying conversation that:
- moved from "sync every file in agent folder" to "sync from a dedicated
  `workspace/` subdir";
- pinned per-agent-type host destinations to the upstream-canonical
  operator-overlay zone, verified from upstream docs at
  hermes-agent.nousresearch.com, docs.openclaw.ai, docs.zeroclawlabs.ai;
- hard-coded a hermes-only exclude list (`config.yaml`, `.env`,
  `auth.json`) so canonical render and workspace overlay write disjoint
  paths under `~/.hermes/`;
- scoped this iteration to Ubuntu (x86_64) with macOS as three follow-up
  subtasks;
- added explicit unit (16), integration (10), and E2E (provision-from-
  scratch on `wolf-i`, three agent types) test cases.
