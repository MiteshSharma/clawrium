# E2E Re-Validation Report — #555 (post-#580/#579/#581 fixes)

**Date:** 2026-05-30
**Branch:** `e2e/555-revalidate-post-fix` off `origin/main`
**Main HEAD:** `060efca` (post-#581 merge)
**Host:** wolf-i (192.168.1.36)
**Provider:** clawrium-glm51 (openrouter / z-ai/glm-5)
**Discord token:** DUMMY (plumbing-only verification — no live bot connection)

## Result matrix — actual re-run

| Agent | Type | Install | Provider | Channel | Chat | Destroy |
|-------|------|---------|----------|---------|------|---------|
| e2e-hermes   | hermes   | ✅ | ✅ | ✅ | ❌ **#582** | ✅ |
| e2e-zeroclaw | zeroclaw | ✅ | ⚠️ **#583** (sync workaround) | ✅ | ✅ | ✅ |
| e2e-openclaw | openclaw | ✅ | ⚠️ #577 ledger-gate fix works; new playbook failure **#583** (sync workaround) | ✅ | ✅ | ✅ |

**Score: 12/15 pass, 1 fail, 2 partial.**

Legend: ✅ pass · ❌ fail · ⚠️ partial / required workaround.

## What works post-fix

- **#576 / PR #579 (zeroclaw gateway.host)** — confirmed. Rendered `config.toml` has `[gateway] host = "0.0.0.0"`. Daemon binds, chat returns real glm-5 reply.
- **#577 / PR #581 (openclaw identity-gate ledger)** — confirmed. Once `--stage identity` is complete, a second `--stage providers` invocation correctly emits `stage 'identity' already complete in onboarding ledger for e2e-openclaw; skipping manual-configure gate` and proceeds (instead of re-blocking on the stale proxy).
- **Openclaw chat** — real glm-5 reply via 41554 after `sync` workaround + ~30s startup grace.
- **Destroy** — clean for all three.

## New regressions / failures found

### #582 — hermes chat still broken (NEW + #575 fix incomplete)

`PR #580` did not fully isolate Discord failure from the FastAPI gateway. Journal on host:

```
ERROR asyncio: Task exception was never retrieved
future: <Task ... exception=LoginFailure('Improper token has been passed.')>
hermes-e2e-hermes.service: Main process exited, code=exited, status=1/FAILURE
```

The LoginFailure propagates as an unhandled asyncio task exception → process exit 1 → systemd restart-loop.

**Compounding issue (NEW):** even with the Discord error caught, the api_server platform refuses to bind:

```
ERROR gateway.platforms.api_server: [Api_Server] Refusing to start:
   binding to 0.0.0.0 requires API_SERVER_KEY.
   Set API_SERVER_KEY or use the default 127.0.0.1.
```

Rendered `.env` on host:
```
API_SERVER_HOST='0.0.0.0'
API_SERVER_KEY=''
```

The clawctl canonical render asks hermes to bind a wildcard with no auth key — hermes upstream correctly refuses. Fix paths in #582.

### #583 — `configure --stage providers` playbook 'failed' with no details (zeroclaw + openclaw)

```
Error: configure stage failed: Configure failed: Configure playbook failed: failed
```

`ansible_runner.run(...)` returns `status: "failed"` with **zero `runner_on_failed` events** and an **empty `private_data_dir`** — no artifacts, no stdout/stderr, no event log. Operator has nothing to debug.

- hermes: not affected — `--stage providers` succeeds for hermes.
- zeroclaw / openclaw: workaround is `clawctl agent sync <name>`, which renders the canonical files correctly and is used today as the post-failure recovery path. But this is not the documented quickstart flow.

## Detailed run log

### Hermes — `e2e-hermes`

1. **Install:** `clawctl agent create e2e-hermes --type hermes --host wolf-i` → ok=28, changed=11. Service unit dropped disabled.
2. **Configure providers:** `--stage providers --provider clawrium-glm51` succeeded. `agent doctor` shows `Resolved provider: clawrium-glm51 (openrouter) api_key=present`.
3. **Channel:** registry record created, `agent channel attach`, `agent sync` succeeded. On-host `~/.hermes/.env` has all three Discord env vars (token / allowed users / require mention).
4. **Chat:** **FAILED.** `Connection failed: Failed to reach hermes at http://192.168.1.36:8679/v1`. systemd journal shows the gateway exiting status=1/FAILURE in a restart loop. Two root causes (see #582).
5. **Destroy:** clean (agent registry record gone, channel record gone, on-host dir removed).

### Zeroclaw — `e2e-zeroclaw`

1. **Install:** ok=16, changed=9. Unit disabled.
2. **Configure providers:** **FAILED** with opaque error (`Configure playbook failed: failed`). See #583.
3. **Recovery + Channel:** `clawctl agent sync` wrote `config.toml` and `zeroclaw-env.conf`. Channel attach + second `sync` succeeded. On-host:
   - `[channels.discord]` block populated with token, allowed_users, mention_only = true.
   - `[gateway]` block has `host = "0.0.0.0"` and `port = 41040` — **#576 fix confirmed**.
4. **Chat:** ✅ `e2e-zeroclaw> Hi there! 👋` — real glm-5 inference.
5. **Destroy:** clean.

### Openclaw — `e2e-openclaw`

1. **Install:** ok=32, changed=16. Gateway token + device credentials captured.
2. **Configure providers (first attempt):** Hit the documented #523 identity gate (expected on a fresh install — `onboarding.identity = pending`).
3. **Configure identity:** `--stage identity` succeeded immediately.
4. **Configure providers (second attempt):** **#577 fix verified** — emitted `stage 'identity' already complete in onboarding ledger for e2e-openclaw; skipping manual-configure gate`. But then the providers playbook itself FAILED with the same opaque error as zeroclaw (#583).
5. **Recovery + Channel:** `sync` wrote `env` and `openclaw.json`. Channel attach + second `sync` succeeded. On-host:
   - `~/.openclaw/env` has `DISCORD_BOT_TOKEN`.
   - `~/.openclaw/openclaw.json` `channels.discord` = `{ enabled: true, allowFrom: ["740723459344302120"], guilds: {} }`.
6. **Chat:** ✅ `e2e-openclaw> Hey there! Good to see you.` — real glm-5. Required ~30s startup grace + a second connection attempt (port 41554 took two restart cycles to bind cleanly).
7. **Destroy:** clean.

## Cleanup

- `clawctl agent get` shows zero `e2e-*` entries.
- All three channel registry records deleted.

## Outcome

- **#576 fix (zeroclaw gateway.host)**: holds.
- **#577 fix (openclaw identity ledger gate)**: holds.
- **#575 fix (hermes Discord isolation)**: **does not fully hold** — see #582.
- Two new sub-issues filed under #555: **#582** (hermes chat), **#583** (configure --stage providers playbook detail-less failure).

The pipeline is **not yet end-to-end green** for all three agent types; 12 of 15 cells pass and the failing cells have clean workarounds (sync) or filed regressions.
