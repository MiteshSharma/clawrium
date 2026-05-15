# Issue 357 — Subtask B Execution Notes

## Architectural Decision: bearer-token data path (B2)

The configure flow renders `config.toml`, starts the daemon, completes the
pairing handshake against the just-started daemon, and persists the resulting
bearer token to `hosts.json` under `agents.<n>.config.gateway.auth`.

Two options were on the table:

- **(a)** add Ansible fact-cache extraction to `configure_agent()` mirroring
  the OpenClaw pattern in `install.py:688-794`, and have `configure.yaml`
  emit the bearer token as a host fact.
- **(b)** have the Python CLI layer make direct HTTP calls
  (`GET /pair/code` → `POST /pair`) against the daemon after `configure_agent()`
  returns, and write the result to `hosts.json` from the CLI.

**Decision: (a).**

Reasons:

1. The pairing handshake must run *after* the daemon is up, which means the
   playbook needs a daemon-startup step + a `/health/providers` readiness probe
   regardless. Doing the `/pair/code` and `/pair` calls one task later — while
   we still hold the SSH/become context — keeps the entire daemon-lifecycle
   sequence in one place. Splitting it (playbook starts daemon, Python finishes
   pairing) creates a brittle ordering contract across two different process
   boundaries.
2. The OpenClaw pattern is the established one in this codebase; mirroring it
   means the same `_resolve_chat_type` → gateway-config reader in
   `cli/chat.py` keeps working without a second hosts.json shape.
3. The CLI host running `clm` may not have direct LAN reachability to the
   agent host's pairing port (the host could sit behind a router that
   forwards SSH but not 4080). Pairing inside the playbook always works
   because it's loopback on the agent host.

Trade-off: configure now extracts Ansible fact cache (new code path in
`configure_agent()`), instead of just driving the playbook. This is small,
matches `install.py`, and is covered by tests.

## Security Considerations (B4)

Default bind in this PR: `host = "0.0.0.0"`, `allow_public_bind = true`,
`require_pairing = true`. Upstream ZeroClaw defaults to `127.0.0.1` and
`allow_public_bind = false`.

### Threat model

LAN-trusted dev / home network. The clm operator's machine and the agent
host are on the same trusted network (homelab, dev LAN). The agent host is
addressable only from peers on that LAN, and the daemon's pairing-token
auth gates every endpoint.

### Why match Hermes' posture

Hermes binds `0.0.0.0` with a 64-char hex `API_SERVER_KEY` (see
`lifecycle.py:780-815`). The reason is identical: cross-LAN `clm chat <n>`
is the entire point — a clm machine connects from any peer on the LAN
without having to set up an SSH tunnel per session. Without bearer-token
enforcement this would be unsafe; with it, the only thing exposed is
"deny unless you hold the bearer token."

### Concretely

- `require_pairing = true` means the gateway rejects every request without
  a paired bearer token (verified against
  `crates/zeroclaw-gateway/src/api_pairing.rs`).
- The bearer token is captured during configure and persisted to
  `hosts.json` under `agents.<n>.config.gateway.auth`. `clm chat` reads
  it back and sends `Authorization: Bearer <token>`.
- Pairing tokens are the auth boundary. There is no TLS — `ws://` is used
  on the LAN. Production / shared-network deployments should layer an SSH
  tunnel (`ssh -L 4080:127.0.0.1:4080 <host>`) and chat via
  `localhost`, but that is operator-configured, not the default for the
  LAN dev experience this PR targets.
- Bearer token is stored at `0600` on disk inside `~/.config/clawrium/`
  (the existing hosts.json mode).

## Frame handling decisions (B5, B7)

For `chat_zeroclaw.py` the wire protocol from
`crates/zeroclaw-gateway/src/ws.rs` is handled as:

| Frame | Behavior |
|---|---|
| `connected`, `session_start` | accepted, no surface output |
| `chunk` | sanitized + accumulated + delivered via `on_delta` |
| `thinking` | sanitized + dim-printed (does not feed the accumulator) |
| `tool_call` | sanitized + dim-printed |
| `tool_result` | sanitized + dim-printed |
| `done` | terminates the turn, returns accumulated text |
| `error` | raises `ChatProtocolError(sanitized_message)` |
| `aborted` | raises `ChatProtocolError("turn aborted")` |
| `chunk_reset` | clears the accumulator (mid-turn reset) |
| `approval_request` | raises `ChatProtocolError(...)` — surfacing inline UX is out of scope for this PR |
| unknown `type` | logged-and-dropped (forward compat) |

All server-supplied text goes through the bidi/control sanitizer
re-exported from `core/chat.py` (renamed `sanitize_server_text` so both
chat backends share it) and `rich.markup.escape` before any
`console.print`.

## Test plan additions (B8)

`tests/test_configure_zeroclaw.py` is rewritten to cover the v0.7.5 schema:

- One `provider`-block-rendering test per provider (anthropic, openai,
  ollama, openrouter) asserting the `kind` discriminator, `model`, and
  `api_key`/`base_url` selection.
- `gateway.host == "0.0.0.0"`, `gateway.allow_public_bind == true`,
  `gateway.require_pairing == true` rendered as the chosen security
  defaults.
- `default_provider` and `default_model` rendered at the top level.

The pre-existing Atlassian integration tests are removed: the v0.7.5
template no longer emits an `[integrations]` block (issue #112 plan
removes it from this template; integrations will land as a follow-up
issue outside #112).

## ATX Round 1 — Bearer-token-at-rest (B7) clarification

The Round 1 reviewer flagged the bearer token being persisted in
`hosts.json` as a credential-storage regression. The decision (and the
mitigating constraints) are:

- `hosts.json` is written exclusively via `core/hosts.py::update_host`
  and its siblings, all of which `os.fchmod(fd, 0o600)` after creation
  (see `core/hosts.py:127, 168, 308, 345`). The file is owner-readable
  only; it is not world-readable at any point.
- OpenClaw already stores its bearer token at the same key path
  (`config.gateway.auth`). Mirroring that shape lets `_extract_gateway_config`
  in `cli/chat.py` route both transports through one reader.
- The issue #112 plan explicitly directs this storage location for
  parity with openclaw (see `.itx/112/00_PLAN.md` "Implications for
  clm" → bearer-token bullet).
- A future hardening pass can migrate both openclaw and zeroclaw
  bearer tokens from hosts.json to `secrets.json` in lockstep; doing
  zeroclaw alone would split the storage convention without a
  corresponding security gain.

The `0600` mode is the load-bearing invariant. Tests covering
`core/hosts.py` already pin it (`test_secrets_*` files); no new test
is required here.

## ATX Round 1 — Idempotent re-pairing (B3) flag surface

Configure now passes `existing_gateway_token` and `force_repair` to the
playbook as Ansible vars:

- When `existing_gateway_token` is present and at least 16 chars, the
  playbook skips the `/pair/code` → `/pair` exchange and echoes the
  existing token back as the cacheable fact. Live `clm chat` sessions
  survive routine reconfigure runs.
- `force_repair: true` overrides the skip and re-mints. Wired today via
  the `extra_vars` parameter on `configure_agent`; CLI surface (a
  `--force-repair` flag on `clm agent configure`) is a small follow-up.
