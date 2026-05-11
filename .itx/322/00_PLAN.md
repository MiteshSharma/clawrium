# Plan — Issue #322: Generalize `clm chat` for hermes via OpenAI-compatible HTTP backend

## Customer Outcome

`clm chat <hermes-name>` opens an interactive REPL that talks to the hermes agent **directly over LAN** using the bearer token, mirroring how `clm chat <openclaw-name>` already works. No SSH tunnel, no port-forward, no curl. Openclaw chat behavior is byte-for-byte unchanged.

## Source-Code Proof (verified against hermes v2026.5.7)

Pulled from `NousResearch/hermes-agent` at the pinned tag:

- `gateway/platforms/api_server.py:56` — `DEFAULT_HOST = "127.0.0.1"` (default only; not a hard bind).
- `gateway/platforms/api_server.py:583` — `self._host = extra.get("host", os.getenv("API_SERVER_HOST", DEFAULT_HOST))` — env var is fully honored.
- `gateway/platforms/api_server.py:3187` — `web.TCPSite(self._runner, self._host, self._port)` — binds whatever address is set.
- `gateway/platforms/api_server.py:3150-3169` — hermes' own startup check refuses to start when `is_network_accessible(host)` is true unless a strong, non-placeholder `API_SERVER_KEY` is configured.

We already generate a 64-char hex `HERMES_API_SERVER_KEY` via `secrets.token_hex(32)` (`core/install.py:547`), so hermes' safety check passes. **Setting `API_SERVER_HOST=0.0.0.0` is supported and gated by the bearer token by hermes itself.** No SSH tunnel needed.

## Architectural Mirror of Openclaw

Openclaw's existing pattern (the contract this issue says to follow):

| Concern | Openclaw today | Hermes (this plan) |
|---|---|---|
| Bind directive in agent config | `bind: "lan"` symbolic token written to `openclaw.json` (`install.py:513`); openclaw resolves it at runtime | `API_SERVER_HOST=0.0.0.0` literal IP via `.env` (`templates/.env.j2:27`); hermes binds directly |
| Where bind value is persisted in hosts.json | `agent_record.config.gateway.bind` | `agent_record.config.api_server.host` |
| Connection target rebuilt at chat-time | `_reconstruct_gateway_url(stored_url, gateway, host_record)` uses `host_record.hostname` + stored port (`cli/chat.py:262-299`) | New `_build_hermes_base_url(api_server, host_record)` — same idea: `http://<host_record.hostname>:<port>/v1` |
| Auth | Token in `gateway.auth` (hosts.json) | Bearer token in `secrets.json` under `HERMES_API_SERVER_KEY` (PR #318's B3 invariant) |
| Transport | WebSocket `ws://...` with custom chat.send RPC | HTTP `POST /v1/chat/completions` (OpenAI-compatible) with SSE streaming |

The only structural difference vs openclaw is the transport itself (HTTP + SSE vs WebSocket), which is unavoidable because the two agents speak different protocols. Everything *else* — bind on all interfaces, token-gated access, clm rebuilds the URL from the host's primary address — is identical.

## Three Concrete Blockers in `cli/chat.py` Today

1. Hard type gate at `cli/chat.py:78` rejects anything that isn't `openclaw`.
2. `OpenClawChatClient` (websocket, challenge/sign, streaming deltas) is the only transport.
3. Gateway config is read from `agent_record.config.gateway.{url,auth}`. Hermes has neither — bind lives in `agent_record.config.api_server.{host,port}`, bearer in `secrets.json`.

## Decisions (defaults locked in)

| Question | Decision | Justification |
|---|---|---|
| Bind address | `0.0.0.0` (all interfaces) on install/configure | Semantic match to openclaw's `bind: "lan"`. Avoids needing clm to know which interface the user reaches the host through (LAN vs Tailscale vs hostname). Hermes' own L3150 safety check enforces a strong bearer token before allowing non-loopback bind, so the token gates the exposure. |
| Connection target | `http://<host_record.hostname>:<api_server.port>/v1` rebuilt per session | Same pattern as `_reconstruct_gateway_url`. `host_record.hostname` is whatever address the user is already reaching the host through, so it's reachable by definition. |
| Conversation state | Single-turn `/v1/chat/completions` with client-side history list | OpenAI-compatible, portable to any future claw with the same endpoint. `/v1/runs` is hermes-specific and complicates the backend abstraction. `--session` becomes a no-op for hermes v1 with a dim warning on non-default values. |
| `features.chat.type` shape | Closed enum `"openai" \| "websocket"` validated by manifest validator | Free strings invite typos. New backends need Python code anyway; bumping the enum is no extra friction. |
| Streaming | SSE via `httpx.AsyncClient.stream()`, fall back to non-stream JSON on non-SSE content-type | UX parity with openclaw streaming. |
| Migration for existing hermes installs | Opportunistic in `lifecycle.configure_agent`: if persisted `api_server.host == "127.0.0.1"`, rewrite to `"0.0.0.0"` before rendering the .env. Existing `HERMES_API_SERVER_KEY` is reused. One `clm agent configure <name>` flips the bind. | No `--force install` needed. The configure restart-handler picks up the rebinded port. |

## Files to Modify / Create

### Modified — make hermes listen on a reachable interface
- `src/clawrium/core/install.py:847-851` — change the persisted `api_server` block to `{"enabled": True, "host": "0.0.0.0", "port": 8642}`. New installs bind 0.0.0.0 from day one.
- `src/clawrium/core/lifecycle.py` (the hermes branch ~lines 734-771) — opportunistic migration: if `persisted_api_server["host"] == "127.0.0.1"`, rewrite the agent record to `"0.0.0.0"` (in-memory + persisted) before merging into `config_data`. One-time, idempotent.

### Modified — chat dispatch + protocol abstraction
- `src/clawrium/platform/registry/hermes/manifest.yaml` — add `features.chat.type: openai`.
- `src/clawrium/platform/registry/openclaw/manifest.yaml` — add `features.chat.type: websocket`.
- `src/clawrium/core/registry.py:130-144, 498-511` — extend `FeaturesConfig` TypedDict and `_validate_features` with `chat: { type: Literal["openai","websocket"] }`.
- `src/clawrium/core/chat.py` — extract a `ChatBackend` Protocol (async `connect`, `send_message`, `close`); `OpenClawChatClient` conforms with zero behavior change.
- `src/clawrium/cli/chat.py` — remove the openclaw type gate (line 78); resolve backend via `features.chat.type`; dispatch to backend-specific config-extraction + REPL.
- `pyproject.toml` — add `httpx>=0.27` to `dependencies` (not currently present; `requests` is sync-only).
- `tests/test_cli_chat.py`, `tests/test_core_chat.py` — split openclaw + hermes sections; add hermes-specific cases.

### New
- `src/clawrium/core/chat_hermes.py` — `HermesOpenAIBackend`:
  - `__init__(base_url, auth_token: SecretStr, timeout: float)`
  - `connect()` — `GET <base>/health` with 5s timeout for fail-fast. Maps connection refused → `ChatConnectionError` with a remediation hint pointing at `systemctl --user status hermes-<name>`.
  - `send_message(message, on_delta, response_timeout_seconds)` — `POST /v1/chat/completions` with `Authorization: Bearer …`, body `{model, messages, stream: true}`. Streams SSE via `httpx.AsyncClient.stream()`, parses `data: {...}` lines, extracts `choices[0].delta.content`. Handles `data: [DONE]` sentinel and `:keep-alive` comments. Falls back to single-JSON-response path on non-SSE content-type.
  - Maintains `self._history: list[dict]` for client-side conversation continuity within a REPL session.
- `tests/test_chat_hermes.py` — backend unit tests.
- `docs/research/aichat.md` — short investigation note (see Investigation section below).

## Code Architecture Sketch

```python
# core/chat.py
class ChatBackend(Protocol):
    async def connect(self) -> None: ...
    async def send_message(self, message: str, *, on_delta: Callable[[str], None] | None,
                           response_timeout_seconds: float) -> str: ...
    async def close(self) -> None: ...

# cli/chat.py (replaces the openclaw type gate)
chat_type = _resolve_chat_type(agent_type)  # reads manifest features.chat.type
if chat_type == "websocket":
    backend = _build_openclaw_backend(agent_record, host_record, ...)  # existing logic, refactored into helper
elif chat_type == "openai":
    backend = _build_hermes_backend(agent_record, host_record, agent_type, agent_name)
else:
    console.print(f"[red]Error:[/red] Chat is not supported for agent type '{agent_type}'.")
    raise typer.Exit(1)

# helper for hermes — mirrors _reconstruct_gateway_url
def _build_hermes_base_url(api_server: dict, host_record: dict) -> str:
    port = int(api_server.get("port") or 8642)
    host = host_record.get("hostname")  # NOT api_server['host'] — that's the bind, not the reach
    return f"http://{host}:{port}/v1"
```

## Steps

1. **Bind address fix (server-side)** — change the install-time `api_server.host` default to `0.0.0.0` in `core/install.py`; add the opportunistic 127.0.0.1→0.0.0.0 migration in the hermes branch of `lifecycle.configure_agent`. Tests in `tests/test_install.py` and `tests/test_lifecycle.py` for both code paths.
2. **Manifest schema** — extend `FeaturesConfig` + `_validate_features` in `core/registry.py`; add `features.chat` to both manifests; reject bogus enums in `tests/test_registry.py`.
3. **httpx dependency** — add `httpx>=0.27` to `pyproject.toml`. Run `make test` to confirm clean lockfile resolution.
4. **`ChatBackend` Protocol** — extract Protocol in `core/chat.py`. `OpenClawChatClient` conforms unchanged. `tests/test_core_chat.py` passes verbatim.
5. **`HermesOpenAIBackend`** — implement in `core/chat_hermes.py` with secret hydration via `get_instance_secrets`, health probe, SSE+JSON `chat.completions`, client-side history.
6. **`cli/chat.py` dispatch** — remove the openclaw gate; add `_build_hermes_backend()` (secret lookup mirroring `lifecycle.py:734-771`, URL construction mirroring `_reconstruct_gateway_url`); friendly errors for missing key / service down. Update `--help` text.
7. **Tests** — split `tests/test_cli_chat.py` into `TestOpenClawChat` (verbatim) + `TestHermesChat` (new); add `tests/test_chat_hermes.py` (backend unit tests).
8. **aichat investigation note** at `docs/research/aichat.md` — 1-page summary covering base-url config, history handling, model selection, error mapping; recommend reference-implementation path; flag aichat-as-sidecar as a possible follow-up.
9. **Manual verify** on a real hermes install: `clm agent configure <hermes-name>` (triggers the bind migration), `clm chat <hermes-name>` for 2-3 turns from a different machine on the LAN, then `clm chat <openclaw-name>` to confirm no regression. Verify `ss -tlnp` on the agent host shows hermes listening on `0.0.0.0:8642`.

## Test Strategy

| Case | Where | Notes |
|---|---|---|
| openclaw chat unchanged | `tests/test_cli_chat.py::TestOpenClawChat` | Existing tests kept verbatim — protocol refactor must not break them |
| New hermes install persists `host: 0.0.0.0` | `tests/test_install.py` | Assert hosts.json `agents.<name>.config.api_server.host` after install |
| Legacy hermes install migrated on configure | `tests/test_lifecycle.py` or `tests/test_hermes_configure.py` | Pre-seed hosts.json with `host: "127.0.0.1"`; call configure flow; assert it's rewritten to `"0.0.0.0"` |
| Migration is idempotent | same | Second configure on an already-migrated record is a no-op |
| hermes chat happy path | `tests/test_cli_chat.py::TestHermesChat::test_happy_path` | Mocks `get_instance_secrets` + httpx; assert URL uses `host_record.hostname`, not `api_server.host` |
| hermes missing `HERMES_API_SERVER_KEY` | `…::test_missing_api_server_key` | secrets.json returns `None` → exit 1 with "Re-run install" |
| hermes service down | `…::test_service_unreachable` | httpx raises `ConnectError` → exit 1 with systemctl remediation hint |
| Manifest enum validation | `tests/test_registry.py` | Reject `features.chat.type: "bogus"` |
| SSE streaming | `tests/test_chat_hermes.py::test_streaming_deltas` | Canned SSE chunks → `on_delta` calls |
| Non-SSE fallback | `…::test_non_streaming_response` | application/json → final-text path |
| `data: [DONE]` and `:keep-alive` handling | `…::test_sse_edge_cases` | Both ignored without spurious `on_delta` calls |
| History accumulation | `…::test_history_grows_across_turns` | Two sequential `send_message` calls → 2nd request body has both prior turns |
| Bearer header | `…::test_bearer_token_header` | Inspect `Authorization` header in mocked request |

Run `make test` and `make lint` before review.

## Risks

- **Bind change exposes the port to the LAN.** That's the whole point, but worth saying out loud. Hermes' own L3150 check refuses to start without a strong key, and our `secrets.token_hex(32)` (64-char hex) passes both their `is_network_accessible` gate and their placeholder-value check. The threat model matches openclaw's existing `bind: "lan"`.
- **Existing hermes installs need one configure pass.** Opportunistic migration handles this transparently. Worst case if the user *doesn't* re-configure: `clm chat` fails with a "service unreachable on `<host-ip>:8642`" error pointing them at `clm agent configure`. No silent data loss.
- **httpx new dependency.** Small, well-maintained, BSD-licensed, FastAPI-ecosystem standard. Pin conservative floor (`>=0.27`).
- **SSE edge cases.** Heartbeats (`:keep-alive`), `data: [DONE]` sentinels, partial JSON across chunks. Covered by handwritten parser + fixtures.
- **`--session` semantic drift.** No-op for hermes v1; print dim warning when user passes non-default value to a hermes agent.

## Subtasks (outcome-driven slices)

Each subtask delivers a user-visible improvement to `clm chat <hermes-name>` and is independently shippable. Earlier slices work without later ones; later slices strictly improve the experience.

### Slice 1 — `clm chat <hermes>` works end-to-end from any clm machine
**User outcome**: I can run `clm chat my-hermes` from my laptop and roundtrip a single message through a hermes agent on another box. No SSH tunnel. No curl. Response prints when the agent finishes.

**Scope** (the minimum that makes this real):
- Flip `core/install.py:847-851` bind from `127.0.0.1` to `0.0.0.0` (new installs).
- Opportunistic migration in `core/lifecycle.py` hermes branch (existing installs flip on next configure).
- Add `features.chat.type` enum to `core/registry.py` + both manifests.
- Add `httpx>=0.27` dep.
- Replace the openclaw type gate in `cli/chat.py` with dispatch by `features.chat.type`.
- New `core/chat_hermes.py` with `HermesOpenAIBackend`: bearer hydration, `POST /v1/chat/completions` (non-streaming for this slice), single-turn (no history yet).
- Enough tests to prove the happy path on hermes and that openclaw chat is unchanged.

**Exit criteria**: a user can chat with hermes from any machine on the LAN; openclaw chat behavior identical.

---

### Slice 2 — multi-turn conversations remember context
**User outcome**: I send "what's 2+2?", agent says "4", I send "double that", agent says "8". Prior turns carry within the REPL session.

**Scope**: client-side history list in `HermesOpenAIBackend.send_message` — each request includes the running `messages: [...]` array. `/reset` command clears it. Tests for two-turn accumulation.

**Exit criteria**: history accumulates across turns; `/reset` clears it.

---

### Slice 3 — responses stream as they're generated
**User outcome**: I see the agent's reply appear word-by-word, same as `clm chat <openclaw-name>` does today, instead of waiting for the full response.

**Scope**: SSE parsing via `httpx.AsyncClient.stream()` against `/v1/chat/completions` with `stream: true`. Handle `data: [DONE]` sentinel and `:keep-alive` comments. Fall back to non-streaming JSON on non-SSE content-type. Wire `on_delta` callback so the existing REPL renderer in `cli/chat.py:186-191` works unchanged.

**Exit criteria**: streaming deltas render incrementally; non-SSE servers still work via fallback.

---

### Slice 4 — failures are obvious and recoverable
**User outcome**: when something's wrong, I get a clear message that tells me how to fix it, not a stack trace.

**Scope** (each failure path gets a friendly message + remediation hint):
- Missing/invalid `HERMES_API_SERVER_KEY` → "Re-run `clm agent install --type hermes`" (mirrors `lifecycle.py:748-754`).
- Service unreachable / connection refused → "Check `systemctl --user status hermes-<name>` on the agent host" plus a hint about `clm agent configure` if the bind looks stale.
- Bearer rejected (401/403) → "Token mismatch. Re-run `clm agent configure <name>`."
- `--session` passed to a hermes agent → dim warning explaining it's a no-op for OpenAI-typed agents.

**Exit criteria**: every failure surface has a tested, helpful message; no raw httpx/network exceptions reach the user.

---

### Slice 5 — aichat investigation note (issue AC, not user-facing)
**User outcome**: future maintainers know why we built our own REPL instead of shelling out to aichat.

**Scope**: `docs/research/aichat.md` — 1-page summary covering base-url config, history handling, model selection, error mapping, and the reference-implementation-vs-sidecar tradeoff. Linked from the issue.

**Exit criteria**: doc exists, linked from #322.

---

### Ordering and parallelism

- Slice 1 is the prerequisite for 2, 3, 4. After Slice 1 lands, hermes chat is *useful but rough*.
- Slices 2, 3, 4 can be developed in parallel after Slice 1 — they touch the same backend file but different methods/paths; rebases will be cheap.
- Slice 5 can land at any time.

A reasonable shipping order: **1 → (2 ‖ 3) → 4 → 5**, with each slice as its own PR so a regression in (e.g.) streaming doesn't block multi-turn from landing.

## Acceptance Criteria Mapping

| AC from issue | Covered by |
|---|---|
| `clm chat <hermes-name>` works | Slice 1 |
| `clm chat <openclaw-name>` unchanged | Slice 1 (regression test) |
| Bearer from secrets.json | Slice 1 |
| Friendly missing-key error | Slice 4 |
| Friendly service-down error | Slice 4 |
| Loopback-only documented (NO LONGER LOOPBACK) | Slice 1 — bind flipped to 0.0.0.0 |
| Multi-turn / streaming UX parity with openclaw | Slices 2 + 3 |
| Test coverage | Each slice ships with its own tests |
| aichat investigation | Slice 5 |

---

<details>
<summary>Prompt Log</summary>

**Stage**: planning (v2 — revised after user pushback)
**Skill**: /itx:plan-create
**Timestamp**: 2026-05-11T00:00:00Z
**Model**: claude-opus-4-7

```prompt
/itx-plan-create 322
```

User pushback on v1: "why does user need to create ssh tunnel? can the chat not directly talk to the server using key and http? have you read the documentation correctly". Verified hermes upstream `api_server.py` honors `API_SERVER_HOST` and self-enforces strong-key requirement for non-loopback binds. Plan revised to mirror openclaw's bind-on-reachable-interface pattern.

</details>
