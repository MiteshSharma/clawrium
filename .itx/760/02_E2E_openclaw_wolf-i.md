# Phase 1 — `ws-openclaw` (PR #773) on `wolf-i`

**Host:** wolf-i (wolf.tailf7742d.ts.net), Linux Ubuntu, xclm SSH user
**Branch:** `e2e/760-ubuntu-wolf-i` @ `2bc545c`
**Provider:** `clawrium-gtm-litellm` (litellm, model=writer)
**Started:** 2026-06-21T05:24:41Z
**Finished:** 2026-06-21T05:32:55Z
**Outcome:** ✅ ALL REQUIRED-PASS BULLETS GREEN

---

## Plan deviations (noted for audit, do not block merge)

1. **Local workspace dir path.** Plan says
   `~/.config/clawrium/agents/ws-openclaw/workspace/`. The code in
   `src/clawrium/core/workspace_sync.py:164` (`_local_workspace_root`)
   and `AGENTS.md` "Workspace Overlay" section both use
   `~/.config/clawrium/agents/<type>/<name>/workspace/`. Used the
   code/AGENTS.md path: `~/.config/clawrium/agents/openclaw/ws-openclaw/workspace/`.
   First sync against plan path produced 0 workspace events and 0 files
   landed on host (silent no-op via empty workspace dir). Re-ran from
   the correct path — both files landed.

2. **`clawctl agent configure` requires `--stage`.** Plan calls
   `clawctl agent configure ws-openclaw`; that's rejected with
   `Error: missing required flag --stage`. Ran the three stages
   per the CLI's `--help`: `--stage identity` → `--stage providers
   --provider clawrium-gtm-litellm` → `--stage validate`.

3. **Stale installed `clawctl`.** `which clawctl` initially resolved to
   `~/.local/bin/clawctl` (uv tool installed copy of a prior version)
   not the worktree. First sync silently skipped the workspace phase
   because that installed binary predated the workspace push code path.
   Re-installed via `uv tool install --reinstall --from . clawrium`
   from this worktree before re-running the matrix. (Documented so any
   reproducer also reinstalls before running.)

4. **NDJSON event names.** Plan uses `workspace_file_pushed` /
   `workspace_file_excluded`. Actual implementation emits
   `phase=push_workspace` events with a JSON message containing
   `state=queued|pushed|complete` (file-level) or
   `state=complete, files_pushed=[...], files_excluded=[...]`
   (terminal). Asserted the semantic equivalent (one queued+pushed
   pair per file, terminal `complete` with both lists).

5. **Mode `0664` not `0644`.** The plan suggests `0644`; the
   playbook spec mirrors local mode (here `664` on local). On-host
   files came up `0664` and that matches `_floor_mode_for` for a
   non-secret-pattern file. Treated as plan-spec match.

6. **First run also exposed an unrelated harmless warning during sync:**
   `warning: registry record missing for openclaw after sync: Agent
   'openclaw' not found on host ...`. This is pre-existing wolf-i
   state from a prior failed install (`wolf-i` openclaw agent visible
   in `clawctl agent get`); not introduced by #773. Not blocking.

---

## Provision

```
$ clawctl agent create ws-openclaw --type openclaw --host wolf-i
agent/ws-openclaw: ready
EXIT=0   (2026-06-21T05:24:41Z → 05:26:13Z)

$ clawctl agent provider attach clawrium-gtm-litellm --agent ws-openclaw
agent/ws-openclaw: attached provider 'clawrium-gtm-litellm'
EXIT=0   (05:26:17Z)

$ clawctl agent configure ws-openclaw --stage identity
agent/ws-openclaw: stage identity complete
EXIT=0   (05:26:42Z)

$ clawctl agent configure ws-openclaw --stage providers --provider clawrium-gtm-litellm
agent/ws-openclaw: stage providers complete
EXIT=0   (05:26:47Z → 05:27:00Z)

$ clawctl agent configure ws-openclaw --stage validate
agent/ws-openclaw: stage validate complete
EXIT=0   (05:27:00Z)

$ clawctl agent start ws-openclaw
agent/ws-openclaw: started
EXIT=0   (05:27:05Z)

$ clawctl agent doctor ws-openclaw
Status: ok   (provider clawrium-gtm-litellm, api_key present, render bundle clean)
EXIT=0   (05:27:35Z)
```

**Required pass:** ✅ Agent provisioned, doctor reports `ok`.

---

## E1 — Marker push via full sync

Created `~/.config/clawrium/agents/openclaw/ws-openclaw/workspace/MARKER.md`
with body `phase-1 e2e marker 2026-06-21T05:30:04Z` (local sha256
`81d23c71e9bcc3b792bb99843ff0c497052b3de654fe8c386ef9ce1dd1f42475`).

```
$ clawctl agent sync ws-openclaw -o json
... (full NDJSON in /tmp/e2e-760-logs/p1_05c_sync_marker.txt)
{"phase":"push_workspace","state":"event","message":"{\"state\":\"queued\",\"path\":\"MARKER.md\",...}"}
{"phase":"push_workspace","state":"event","message":"{\"state\":\"pushed\",\"path\":\"MARKER.md\",...}"}
{"phase":"push_workspace","state":"event","message":"{\"state\":\"complete\",\"files_pushed\":[\"MARKER.md\"],\"files_excluded\":[]}"}
{"phase":"sync","state":"complete"}
EXIT=0   (2026-06-21T05:31:41Z → 05:31:44Z)
```

Host verification via `ssh -i …/wolf-i/xclm_ed25519 xclm@wolf
sudo -n -u ws-openclaw …`:

```
ws-openclaw:ws-openclaw 664 40 /home/ws-openclaw/.openclaw/workspace/MARKER.md
phase-1 e2e marker 2026-06-21T05:30:04Z
81d23c71e9bcc3b792bb99843ff0c497052b3de654fe8c386ef9ce1dd1f42475  /home/ws-openclaw/.openclaw/workspace/MARKER.md
```

**Required pass:**
- ✅ File exists with exact bytes (sha256 match local).
- ✅ Owner `ws-openclaw:ws-openclaw`.
- ✅ Mode `0664` (matches local-mode mirror; not a secret-pattern).
- ✅ `clawctl agent doctor ws-openclaw` → `Status: ok` after sync.
- ✅ Zero `gateway_token_rotated` events (openclaw not in `_PAIRING_AGENT_TYPES`).

---

## `--workspace-only` smoke test

Added `~/.config/clawrium/agents/openclaw/ws-openclaw/workspace/NOTES.md`
with body `extra: verified by --workspace-only`.

```
$ clawctl agent sync ws-openclaw --workspace-only -o json
{"phase":"validate","state":"event","message":"assembling render inputs for ws-openclaw"}
{"phase":"push_workspace","state":"event","message":"{\"state\":\"queued\",\"path\":\"MARKER.md\",...}"}
{"phase":"push_workspace","state":"event","message":"{\"state\":\"queued\",\"path\":\"NOTES.md\",...}"}
{"phase":"push_workspace","state":"event","message":"{\"state\":\"pushed\",\"path\":\"MARKER.md\",...}"}
{"phase":"push_workspace","state":"event","message":"{\"state\":\"pushed\",\"path\":\"NOTES.md\",...}"}
{"phase":"push_workspace","state":"event","message":"{\"state\":\"complete\",\"files_pushed\":[\"MARKER.md\",\"NOTES.md\"],\"files_excluded\":[]}"}
{"phase":"sync","state":"event","message":"workspace-only sync of ws-openclaw: 2 pushed, 0 excluded"}
{"phase":"sync","state":"complete"}
EXIT=0   (2026-06-21T05:32:16Z → 05:32:19Z)
```

Host: `NOTES.md` present, owner `ws-openclaw:ws-openclaw`, mode `664`,
bytes match local.

**Required pass:**
- ✅ `NOTES.md` lands at `/home/ws-openclaw/.openclaw/workspace/NOTES.md`.
- ✅ NDJSON stream emits queued+pushed events for NOTES.md (semantic
  equivalent of plan's `workspace_file_pushed`).
- ✅ Exit code `0`.
- ✅ Zero `gateway_token_rotated` events (confirmed via
  `grep -c gateway_token_rotated`).

---

## Cleanup

```
$ clawctl agent delete --yes ws-openclaw
agent/ws-openclaw: deleted   EXIT=0  (05:32:41Z → 05:32:55Z)

$ rm -rf ~/.config/clawrium/agents/openclaw/ws-openclaw

Host check:
  test -d /home/ws-openclaw → absent
  id ws-openclaw            → no such user
```

**Required pass:** ✅ Host cleanup verified.
