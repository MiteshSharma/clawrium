# Phase 3 — `ws-hermes` (PR #775) on `wolf-i` — THE CRITICAL ONE

**Host:** wolf-i (wolf.tailf7742d.ts.net), Linux Ubuntu, xclm SSH user
**Branch:** `e2e/760-ubuntu-wolf-i` @ `2bc545c`
**Provider:** `clm-openrouter` (openrouter, model=openai/gpt-4o, role=primary)
**Started:** 2026-06-21T05:41:32Z
**Finished:** 2026-06-21T05:46:40Z
**Outcome:** ✅ ALL REQUIRED-PASS BULLETS GREEN — including the
user-emphasized invariant: **excluded files do not propagate, neither
on ADD nor on MODIFY**.

Same plan-vs-CLI deviations as Phase 1/2 noted up front
([02_E2E_openclaw_wolf-i.md](02_E2E_openclaw_wolf-i.md)). Additional
hermes-specific path adjustment: the plan's hostile `state.db-journal`
is not present on the host baseline (SQLite WAL mode means only
`state.db`, `state.db-shm`, `state.db-wal` exist as live companions —
the journal file only appears in rollback-journal mode). Verified
unchanged-or-still-absent semantically.

---

## Provision

```
$ clawctl agent create ws-hermes --type hermes --host wolf-i
agent/ws-hermes: installed (2026.5.29.2) → ready    EXIT=0

$ clawctl agent provider attach clm-openrouter --agent ws-hermes --role primary
attached

$ clawctl agent configure ws-hermes --stage identity      → complete
$ clawctl agent configure ws-hermes --stage providers --provider clm-openrouter → complete
$ clawctl agent configure ws-hermes --stage validate      → complete
$ clawctl agent start ws-hermes  → started
$ clawctl agent doctor ws-hermes → Status: ok
```

---

## Baseline capture (`/tmp/e2e-hermes-baseline/`)

```
65ede2085206125ac196b845af2a6539916949a9dd1030bba3266ea34629051c  /home/ws-hermes/.hermes/config.yaml
7ab0d09940a40239bf9c721a1b592556bf164478f45513d48bb447a7f59c074a  /home/ws-hermes/.hermes/.env
ABSENT /home/ws-hermes/.hermes/auth.json
5c9dec1886cc01f5f2307ee1ea87f9b32a4cef0f8f9a2c68beebc558013bedab  /home/ws-hermes/.hermes/state.db
ABSENT /home/ws-hermes/.hermes/state.db-journal
27ff631657681ffb2c14ce6322216712c088d1f70f7cad25a019fc6227487c9f  /home/ws-hermes/.hermes/state.db-wal
e4acc7ab712f430aa0144c898e8f8950cd68861a2d1a6f5833b628251c68ec86  /home/ws-hermes/.hermes/state.db-shm
NO_SKILLS_CLAWRIUM_DIR
(sessions/ and logs/ empty for this fresh install)
```

Also persisted the canonical `config.yaml` body to
`/tmp/e2e-hermes-baseline/config.yaml` (258 bytes, sha256 matches
host) for the MODIFY test.

---

## Good-files test (positive)

Dropped:
- `~/.config/clawrium/agents/hermes/ws-hermes/workspace/profiles/coder/SOUL.md` = `phase-3 e2e SOUL`
- `~/.config/clawrium/agents/hermes/ws-hermes/workspace/memories/NOTES.md` = `phase-3 e2e NOTES`

```
$ clawctl agent sync ws-hermes -o json     (05:44:31Z → 05:44:39Z)
  push_workspace queued/pushed memories/NOTES.md
  push_workspace queued/pushed profiles/coder/SOUL.md
  push_workspace complete files_pushed=2 files_excluded=[]
EXIT=0
```

Host:
```
45f872d1ac2e172ea7175b32ace51119ae8bd9141268830baf059e020365c6a5  /home/ws-hermes/.hermes/memories/NOTES.md
fc09ed47f7c277d53baa9189a06902f532b6e4137fe260e1a1d132600a9f8d4a  /home/ws-hermes/.hermes/profiles/coder/SOUL.md
```

**Required pass:**
- ✅ Both files landed at correct paths.
- ✅ Two push events (one per file), semantic equivalent of plan's
  `workspace_file_pushed`.
- ✅ Zero `gateway_token_rotated` events (hermes does not rotate).

---

## Hostile ADD test — 10 excluded files all rejected

Dropped malicious bytes for all 10 exclude-list paths:

```
.env                              ← MALICIOUS_KEY=stolen
config.yaml                       ← MALICIOUS: overwrites canonical
auth.json                         ← {"malicious":true}
state.db                          ← MALICIOUS-DB
state.db-journal                  ← MALICIOUS-JOURNAL
state.db-wal                      ← MALICIOUS-WAL
state.db-shm                      ← MALICIOUS-SHM
sessions/123.json                 ← {"malicious_session":true}
logs/gateway.log                  ← MALICIOUS log line
skills/clawrium/tdd/SKILL.md      ← MALICIOUS SKILL
```

```
$ clawctl agent sync ws-hermes -o json     (05:44:56Z → 05:45:04Z)
NDJSON (one per file):
  push_workspace excluded .env                             reason=manifest_exclude
  push_workspace excluded auth.json                        reason=manifest_exclude
  push_workspace excluded config.yaml                      reason=manifest_exclude
  push_workspace excluded state.db                         reason=manifest_exclude
  push_workspace excluded state.db-journal                 reason=manifest_exclude
  push_workspace excluded state.db-shm                     reason=manifest_exclude
  push_workspace excluded state.db-wal                     reason=manifest_exclude
  push_workspace excluded logs/gateway.log                 reason=manifest_exclude
  push_workspace excluded sessions/123.json                reason=manifest_exclude
  push_workspace excluded skills/clawrium/tdd/SKILL.md     reason=manifest_exclude
  push_workspace queued/pushed memories/NOTES.md
  push_workspace queued/pushed profiles/coder/SOUL.md
  push_workspace complete files_excluded=10 files_pushed=2
EXIT=0
```

Host sha256 diff vs baseline:
```
$ diff /tmp/e2e-hermes-baseline/baseline.txt /tmp/e2e-hermes-baseline/post_add.txt
(only timestamp header + an unrelated find-stderr ordering line differ — every sha256 is unchanged)
```

Detailed re-check:
```
65ede2085206125ac196b845af2a6539916949a9dd1030bba3266ea34629051c  /home/ws-hermes/.hermes/config.yaml      ← UNCHANGED
7ab0d09940a40239bf9c721a1b592556bf164478f45513d48bb447a7f59c074a  /home/ws-hermes/.hermes/.env             ← UNCHANGED
ABSENT /home/ws-hermes/.hermes/auth.json                                                                  ← STILL ABSENT
5c9dec1886cc01f5f2307ee1ea87f9b32a4cef0f8f9a2c68beebc558013bedab  /home/ws-hermes/.hermes/state.db         ← UNCHANGED
ABSENT /home/ws-hermes/.hermes/state.db-journal                                                           ← STILL ABSENT (WAL mode)
27ff631657681ffb2c14ce6322216712c088d1f70f7cad25a019fc6227487c9f  /home/ws-hermes/.hermes/state.db-wal     ← UNCHANGED
e4acc7ab712f430aa0144c898e8f8950cd68861a2d1a6f5833b628251c68ec86  /home/ws-hermes/.hermes/state.db-shm     ← UNCHANGED
NO_SKILLS_CLAWRIUM_DIR                                                                                    ← W10 iter-3 invariant holds
sessions: empty                                                                                           ← UNCHANGED
logs: empty                                                                                               ← UNCHANGED
```

**Required pass:**
- ✅ Each of the 10 hostile files emits exactly one
  `state=excluded, reason=manifest_exclude` event.
- ✅ Zero "pushed" events for any of those 10 paths
  (only NOTES.md and SOUL.md show pushed).
- ✅ Every canonical file's sha256 UNCHANGED.
- ✅ Daemon-managed files (state.db + WAL companions) UNCHANGED.
- ✅ No `/home/ws-hermes/.hermes/skills/clawrium/tdd/SKILL.md` — the
  W10 iter-3 invariant holds.

---

## Hostile MODIFY test (the user-emphasized case)

Took the EXACT canonical `config.yaml` body (sha256 `65ede208...`) from the
host baseline. Appended one line `# malicious-modify-test` to the
LOCAL workspace copy. Removed every other ADD-test artifact to
isolate the modify-only effect.

```
Local sha256: 4d7450cb1104c3c4300074d349a0405ba49aeb21ac4399515bfc5e40b9634a86
Baseline sha: 65ede2085206125ac196b845af2a6539916949a9dd1030bba3266ea34629051c   ← differs
Local workspace: config.yaml, memories/NOTES.md, profiles/coder/SOUL.md
```

```
$ clawctl agent sync ws-hermes -o json     (05:45:28Z → 05:45:33Z)
  push_workspace excluded config.yaml                      reason=manifest_exclude
  push_workspace queued/pushed memories/NOTES.md
  push_workspace queued/pushed profiles/coder/SOUL.md
  push_workspace complete files_pushed=2 files_excluded=["config.yaml"]
EXIT=0
```

Host:
```
$ sha256sum /home/ws-hermes/.hermes/config.yaml
65ede2085206125ac196b845af2a6539916949a9dd1030bba3266ea34629051c  /home/ws-hermes/.hermes/config.yaml
$ tail -3 /home/ws-hermes/.hermes/config.yaml
auxiliary:
  title_generation:
    model: "anthropic/claude-haiku-4.5"
```

The trailing `# malicious-modify-test` line is NOT on host. sha256
matches the baseline byte-for-byte.

**Required pass:**
- ✅ `state=excluded, path=config.yaml, reason=manifest_exclude` emitted.
- ✅ On-host sha256 matches baseline (`65ede208...`). **The
  modification did not propagate. This is the failure mode the user
  explicitly asked to be verified, and it is held by the exclude
  filter.**

---

## Symlink bypass attempt

Created `workspace/innocent.md` → `/etc/passwd` symlink (innocuous
name, sensitive-content target).

```
$ ln -sf /etc/passwd ~/.config/clawrium/agents/hermes/ws-hermes/workspace/innocent.md
$ clawctl agent sync ws-hermes -o json     (05:45:51Z → 05:45:55Z)
  push_workspace skipped innocent.md   reason=symlink
  push_workspace queued/pushed memories/NOTES.md
  push_workspace queued/pushed profiles/coder/SOUL.md
  push_workspace complete files_pushed=2 files_excluded=[]
EXIT=0
```

Host check:
```
$ ls -la /home/ws-hermes/.hermes/innocent.md
ls: cannot access '/home/ws-hermes/.hermes/innocent.md': No such file or directory
NOT_PRESENT
$ sha256sum /home/ws-hermes/.hermes/config.yaml
65ede2085206125ac196b845af2a6539916949a9dd1030bba3266ea34629051c   ← still baseline
$ ls -la /home/ws-hermes/.hermes/auth.json
NO_AUTH_JSON   ← still absent (was absent at baseline)
```

`clawctl agent doctor ws-hermes` → `Status: ok`.

**Required pass:**
- ✅ Symlink rejected at enumeration with
  `state=skipped, reason=symlink` (preferred path).
- ✅ No `innocent.md` on host.
- ✅ `auth.json` (the realistic sensitive target the symlink could
  have aliased) is still absent — exclude list AND symlink rejection
  both held.

---

## Cleanup

```
$ clawctl agent delete --yes ws-hermes → deleted    EXIT=0
$ rm -rf ~/.config/clawrium/agents/hermes/ws-hermes
$ id ws-openclaw ws-zeroclaw ws-hermes → no such user (all three)
```

`clawctl agent get` after cleanup: only the pre-existing fleet
(`wolf-i` failed openclaw, espresso, clawrium-d01, clawrium-triage,
clawrium-gtm, clawrium-exec, clawrium-maurice, hermes-mac). No
ws-* leftovers. Pre-existing fleet untouched.
