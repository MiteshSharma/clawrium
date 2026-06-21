# Phase 2 — `ws-zeroclaw` (PR #774) on `wolf-i`

**Host:** wolf-i (wolf.tailf7742d.ts.net), Linux Ubuntu, xclm SSH user
**Branch:** `e2e/760-ubuntu-wolf-i` @ `2bc545c`
**Provider:** `clawrium-glm51` (openrouter, model=z-ai/glm-5)
**Started:** 2026-06-21T05:33:00Z
**Finished:** 2026-06-21T05:40:32Z
**Outcome:** ✅ ALL REQUIRED-PASS BULLETS GREEN

Same plan-vs-CLI deviations as Phase 1 (configure stages, workspace
path, event-name shape) — see [02_E2E_openclaw_wolf-i.md](02_E2E_openclaw_wolf-i.md).
Additional zeroclaw-specific note: the configure stages must run
`providers → identity → providers (retry) → validate` because the
first `--stage providers` call falls back to a manual identity prompt
(known limitation tracked in #523), but the failed call still advances
the on-ledger state so the second providers call after identity
completes succeeds. Captured both runs in the log file.

---

## Provision

```
$ clawctl agent create ws-zeroclaw --type zeroclaw --host wolf-i
agent/ws-zeroclaw: installed (0.7.5) → ready    EXIT=0
$ clawctl agent provider attach clawrium-glm51 --agent ws-zeroclaw
attached
$ clawctl agent configure ws-zeroclaw --stage identity      → complete
$ clawctl agent configure ws-zeroclaw --stage providers --provider clawrium-glm51 → complete
$ clawctl agent configure ws-zeroclaw --stage validate      → complete
$ clawctl agent start ws-zeroclaw
  gateway_token_rotated reason=start  (initial pairing event, expected)
  → started
$ clawctl agent doctor ws-zeroclaw → Status: ok
```

---

## E2 — Bearer-rotation matrix (full sync)

Captured bearer sha256 BEFORE sync from
`hosts.json.agents.ws-zeroclaw.config.gateway.auth`:

```
PRE_SHA256: 3a673152f1a92edbb497f244832a087dca5c663110664170512a45ceb6e3f657
```

Dropped operator-override `profiles/coder/SOUL.md` (40 bytes, sha256
`52537ee12209eb28603e9db4088854b4b6290e4f53e8911575daaab92f674e63`).

```
$ clawctl agent sync ws-zeroclaw -o json     (2026-06-21T05:35:45Z → 05:35:57Z)
  push_workspace queued/pushed profiles/coder/SOUL.md
  push_workspace complete files_pushed=["profiles/coder/SOUL.md"]
  restart zeroclaw-ws-zeroclaw.service
  repair re-pairing zeroclaw gateway for ws-zeroclaw
  gateway_token_rotated reason=sync   ← EXACTLY ONE
  synced ws-zeroclaw: 2 written, 0 unchanged
EXIT=0

POST_SHA256_1: 31fdf6e23ce14bef2f0de93a0663ae60ad1d68357671d24bd7b48ee37d1ec253
```

Host (`sudo -n -u ws-zeroclaw ...`):
```
phase-2 e2e operator-override SOUL bytes
52537ee12209eb28603e9db4088854b4b6290e4f53e8911575daaab92f674e63  /home/ws-zeroclaw/.zeroclaw/workspace/profiles/coder/SOUL.md
```

**Required pass:**
- ✅ SOUL.md on host at correct path, operator bytes (sha256 match local).
- ✅ Pre vs post sha256 differs (`3a67...` → `31fd...`).
- ✅ Exactly one `gateway_token_rotated` NDJSON event (`grep -c` → 1).
- ✅ `clawctl agent doctor ws-zeroclaw` Status: ok.

---

## `--workspace-only` also rotates

```
$ clawctl agent sync ws-zeroclaw --workspace-only -o json     (05:36:17Z → 05:36:25Z)
  push_workspace queued/pushed profiles/coder/SOUL.md
  push_workspace complete
  repair re-pairing zeroclaw gateway for ws-zeroclaw (workspace-only sync)
  gateway_token_rotated reason=workspace-only-sync   ← EXACTLY ONE
  workspace-only sync of ws-zeroclaw: 1 pushed, 0 excluded
EXIT=0

POST_SHA256_2: 9db42a7849832526e60e59940c02fca6ccebf5b3401cbcf7a64efc5910b49bc6
```

**Required pass:**
- ✅ POST_SHA256_2 differs from POST_SHA256_1 (`31fd...` → `9db4...`).
- ✅ Exactly one `gateway_token_rotated` event (reason=`workspace-only-sync`).

---

## Negative pin — openclaw `--workspace-only` does NOT rotate

Re-provisioned `ws-openclaw` (same flow as Phase 1), seeded
`workspace/PIN.md`, then:

```
$ clawctl agent sync ws-openclaw --workspace-only -o json   (05:39:22Z → 05:39:30Z)
  push_workspace queued/pushed PIN.md
  push_workspace complete files_pushed=["PIN.md"]
  workspace-only sync of ws-openclaw: 1 pushed, 0 excluded
EXIT=0
```

`grep -c gateway_token_rotated` → **0**.

**Required pass:** ✅ Zero `gateway_token_rotated` events (openclaw not
in `_PAIRING_AGENT_TYPES`).

Cleanup: `clawctl agent delete --yes ws-openclaw` → deleted.

---

## `--workspace-only --dry-run`

```
$ clawctl agent sync ws-zeroclaw --workspace-only --dry-run -o json   (05:40:03Z)
{"phase":"sync","state":"dry-run complete"}
EXIT=0
```

`grep -c gateway_token_rotated` → **0**.

**Required pass:** ✅ Zero rotation events in `--check`-mode dry-run.
The CLI short-circuits before the workspace+rotation phases (the
defense-in-depth `dry_run` gate at `lifecycle_canonical.py:825`
would also block rotation if the CLI did reach that branch).

---

## Cleanup

```
$ clawctl agent doctor ws-zeroclaw → Status: ok (post-rotations)
$ clawctl agent delete --yes ws-zeroclaw → deleted     EXIT=0
$ rm -rf ~/.config/clawrium/agents/zeroclaw/ws-zeroclaw
```
