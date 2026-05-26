# Issue #501 — Multi-provider attachments for hermes (primary + auxiliary slots)

## What's supported today across the three agent types

| Agent type | Provider attachment | Multi-provider use? | Auxiliary roles? |
|---|---|---|---|
| **zeroclaw** | `agent.providers: [name]`, singleton enforced (`agent provider attach` rejects second; `lifecycle.py:957-966` re-asserts) | No — the gateway daemon binds one inference target. | None. |
| **openclaw** | Same singleton attachment via `agent.providers`. `config.provider` overlay = single dict. | No — openclaw templates assume one provider. | None. |
| **hermes** | Same singleton attachment today. `hermes.env.j2` emits the single active provider's API key; `hermes-config.yaml.j2` hardcodes per-`provider_type` `auxiliary.title_generation.model` only. | **Should be multi.** Upstream supports many keys in `.env` and 9 auxiliary slots per `hermes_cli/config.py:716-794`. | **9 slots, defined upstream.** |

**Conclusion:** the multi-provider concept lives entirely on the hermes side. openclaw and zeroclaw stay singleton (their existing constraint stands). Scope this issue to hermes; preserve the singleton invariant on the other two.

## Upstream surface confirmed (hermes v2026.5.7)

### Auxiliary slots (9 total)

From `NousResearch/hermes-agent/hermes_cli/config.py:716-794`:

| Slot | Default timeout | Extra fields |
|---|---|---|
| `vision` | 120s | `download_timeout`, `extra_body` |
| `web_extract` | 360s | — |
| `compression` | 120s | — |
| `session_search` | 30s | `max_concurrency: 3` |
| `skills_hub` | 30s | — |
| `approval` | 30s | — |
| `mcp` | 30s | — |
| `title_generation` | 30s | — |
| `curator` | 600s | — |

Each slot shape: `{ provider, model, base_url, api_key, timeout, extra_body }`.

`auxiliary.<slot>.provider` is **not enum-restricted**: any provider name resolves against the top-level `providers:` dict (or `custom_providers`). `"auto"` means inherit the main chat provider/credentials. clawctl can pass any of its own provider-type names here.

### Provider types clawctl currently supports

From `src/clawrium/core/providers/models.json`: `anthropic`, `bedrock`, `ollama`, `openai`, `openrouter`, `vertex`, `zai` (7 types).

The hermes env template today emits credentials for 5 of 7 — `anthropic`, `openai`, `openrouter`, `bedrock`, `ollama`. **`vertex` and `zai` are gaps on the hermes path today**, pre-existing — flag as a follow-up; not in scope here.

### Provider → env-var mapping

| clawctl provider type | Env var(s) | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | |
| `openai` | `OPENAI_API_KEY` | |
| `openrouter` | `OPENROUTER_API_KEY` | upstream's default path |
| `bedrock` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | secret pair |
| `ollama` | *(none)* | local; base_url instead |
| `vertex` | not emitted | gap (out of scope) |
| `zai` | not emitted | gap (out of scope) |

## Current command surface relevant to this change

- `clawctl agent provider attach <name> --agent <a>` — singleton-enforced (`agent/provider.py:106-118`).
- `clawctl agent provider detach <name> --agent <a>` — preserves `config.provider` as last-known-good (deliberate, #426).
- `clawctl agent provider get --agent <a>` — table/json/yaml/name output.
- `clawctl agent configure <a>` `providers` stage runs `provider_select` + `provider_test` from the manifest (same wiring for all three agent types).
- `lifecycle.py:945-1024` bridges `agent.providers` (attach list) → `config.provider` (the dict templates read), with the singleton check at 957-966.
- Hermes templates: `hermes.env.j2` (env file) + `hermes-config.yaml.j2` (YAML config). Both currently single-provider.

## Proposed changes

### 1. Data model (versioned schema bump)

Today: `agent.providers: ["my-anthropic"]` (list of names, singleton).

Proposed (hermes only): `agent.providers: [{ "name": "my-anthropic", "role": "primary", "model": "claude-…" }, { "name": "dgx-ollama", "role": "compression", "model": "qwen-…" }]`.

- Invariants: exactly one `role: primary`; auxiliary roles unique within the list; `role` ∈ {`primary`, `vision`, `web_extract`, `compression`, `session_search`, `skills_hub`, `approval`, `mcp`, `title_generation`, `curator`} (10 values total — primary + 9 upstream slots).
- Migration: on load, list-of-strings → `[{name, role: "primary", model: <provider.default_model>}]`. Forward-only.
- For zeroclaw/openclaw the storage shape stays list-of-strings; migration is gated on agent type. Their singleton invariant is preserved end-to-end.

### 2. CLI surface

Asymmetric by design: hermes-only multi; zeroclaw/openclaw retain singleton.

```
clawctl agent provider attach <provider-name> \
    --agent <a> \
    [--role <role>] \
    [--model <model-id>]

clawctl agent provider detach <provider-name> --agent <a>

clawctl agent provider set-role <provider-name> \
    --agent <a> \
    --role <role>

clawctl agent provider get --agent <a> [--output table|json|yaml|name]
```

**Decisions locked:**

- **Q1 — asymmetric singleton:** keep. hermes allows multi; zeroclaw and openclaw retain their singleton invariant (existing error path unchanged). `--role` is rejected when target agent is not hermes.
- **Q2 — `set-role` as a new verb:** keep. hermes-specific, fine to introduce a new verb not present on `skill`/`integration`/`channel`. Rejected on non-hermes agents.
- **Q3 — `--model` default:** defaults to the provider's `default_model` from `~/.config/clawrium/providers.json` when omitted. Explicit override per attachment supported via `--model`.

**Behavior details:**

- `attach`: `--role` defaults to `primary` if no primary yet; required when primary exists. Rejects role collision (auxiliary slot already filled) with a hint pointing at `set-role`.
- `detach`: rejects detaching `primary` unless another attachment is first promoted via `set-role`.
- `set-role`: hermes-only; supports promoting an auxiliary to primary (the old primary must be moved or detached first to keep the exactly-one-primary invariant).
- `get`: extend rows with `ROLE` and `MODEL` columns; json/yaml shape gains `role` and `model` keys.

### 3. Configure stage extension

The manifest `providers` stage today is `provider_select` + `provider_test`. For hermes, drive an extended interactive flow that:

1. Picks the primary provider (existing flow).
2. Loops offering to attach auxiliary providers to each of the 9 slots (skippable; default no).
3. Runs `provider_test` against the **primary** plus each newly attached auxiliary attachment.

Prefer a manifest hint (`onboarding.stages.providers.multi: true`) over a new task type, to keep the task-type vocabulary stable while the dispatcher branches on the hint. zeroclaw/openclaw manifests stay without the hint and behave as today.

### 4. Reconcile / lifecycle bridge

`core/lifecycle.py:945-1024` — split the bridge by agent type:

- zeroclaw/openclaw: unchanged singleton path.
- hermes: drop the singleton check; build a `config.providers` list (one entry per attachment with name/type/role/model/endpoint/credentials reference). Continue to populate `config.provider` from the primary entry for back-compat with the bridge contract.

`_run_providers_stage` in `cli/agent.py:402+` stores the **primary** provider name into `providers_stage.provider_id` (existing single-provider invariant in onboarding state). Auxiliary attachments are tracked solely in `agent.providers` — no schema change to onboarding state.

### 5. Template changes

**`templates/hermes.env.j2`:**

- Replace the single `if/elif provider.type` ladder with a loop over `config.providers`. Emit each provider type's expected env var (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AWS_ACCESS_KEY_ID/SECRET/REGION` for bedrock). Skip Ollama (no key).
- Key conflict policy: if two attachments share the same provider type (e.g. two Anthropic keys), the **primary wins**; warn at configure time.
- Keep `HERMES_INFERENCE_PROVIDER` driven by primary.

**`templates/hermes-config.yaml.j2`:**

- `model.default` and `model.provider` driven by primary attachment.
- Replace the hardcoded `auxiliary.title_generation.model` block with a generated `auxiliary:` block iterating all non-primary attachments and emitting `<slot>.provider` + `<slot>.model` matching upstream `hermes_cli/config.py:716-794` shape.
- Slots without an attachment: omit entirely (hermes falls back to its default).

### 6. Validation

- Reuse `provider_test` per attachment in the configure flow.
- Post-deploy `/health` probe unchanged.
- Per-slot smoke (a chat call exercising each auxiliary provider through hermes) — defer to follow-up unless cheap.

## Files to modify

- `src/clawrium/cli/clawctl/agent/provider.py` — extend `attach`/`detach`/`get`, add `set-role`. Branch on agent type for hermes-only behavior.
- `src/clawrium/core/lifecycle.py` — split provider-bridge by agent type; build `config.providers` for hermes.
- `src/clawrium/core/hosts.py` — schema migration helper for hermes provider attachments.
- `src/clawrium/cli/agent.py` (`_run_providers_stage`, `_sync_provider_config`) — multi-attach interactive flow + sync payload extension for hermes.
- `src/clawrium/platform/registry/hermes/manifest.yaml` — slot enumeration + `multi: true` hint.
- `src/clawrium/platform/registry/hermes/templates/hermes.env.j2` — loop over providers.
- `src/clawrium/platform/registry/hermes/templates/hermes-config.yaml.j2` — render `auxiliary.<slot>` from attachments.
- `src/clawrium/platform/registry/hermes/playbooks/configure.yaml` — pass the providers list through to Ansible vars.
- Tests under `tests/` — provider attach/detach/set-role, lifecycle bridge, env+config template rendering.
- `docs/installation.md` + hermes docs — multi-provider configure walkthrough.

## Test strategy

- Unit: schema migration round-trip; attach with/without role; primary-detach rejection; multi-type env emission; auxiliary-slot YAML emission for each provider type; non-hermes agent rejects `--role` and `set-role`.
- Snapshot: render `.env` and `config.yaml` for fixture (primary=anthropic + compression=ollama@DGX + title_generation=openai).
- Integration (per AC): hermes on a non-DGX host, cloud anthropic primary + DGX-hosted ollama in `compression`; verify `/health` and exercise the compression path.

## Risks / open questions

1. **Singleton enforcement in lifecycle.py is a hard error today.** Removing it for hermes risks regressions if `agent.providers` contains stale entries from a failed attach. Mitigation: schema migration normalizes stray list-of-strings to a single primary record before the bridge runs.
2. **Credential conflicts when two attachments share a type.** Hermes' `.env` has one slot per env-var name; can't carry two `ANTHROPIC_API_KEY`s. "Primary wins" must be explicit and surfaced at configure time. Per-slot credential overrides would require upstream support and are out of scope.
3. **`config.provider` (singular) is still read by openclaw/zeroclaw templates** — keep populated for hermes too (from primary) to avoid breaking the bridge contract.
4. **No fallback chain** (explicitly out of scope in the issue). Slot-to-provider mapping is 1:1.
5. **`vertex` and `zai` provider types** are clawctl-supported but not emitted by the hermes env template today. Pre-existing gap; not in scope. Flag as a follow-up.
6. **Repo-wide `clm` → `clawctl` drift** in comments and manifest text (e.g. `manifest.yaml:17,43,50,51`, `agent/provider.py:5`). Cosmetic; out of scope, track as cleanup.

## High-level execution workflow

Five phases, one PR each. Phases 1–3 are independently mergeable; 4 depends on 1+3; 5 closes the issue.

### Phase 1 — Schema + data model foundation
Goal: `agent.providers` holds objects for hermes, strings for others, no user-visible change.
1. Migration in `core/hosts.py`: hermes list-of-strings → `[{name, role: "primary", model: <provider.default_model>}]`.
2. Validation helpers: enforce role uniqueness + exactly-one-primary for hermes.
3. Bridge in `lifecycle.py` branches on agent type; hermes path builds `config.providers` + still populates `config.provider` from primary.
4. Verify: existing tests pass; new tests for migration + bridge.

### Phase 2 — CLI surface
Goal: attach/detach/set-role/get work end-to-end on storage.
1. Extend `cli/clawctl/agent/provider.py`: `--role`, `--model` on `attach`; new `set-role`; extended `detach` (primary-protected); extended `get` output.
2. Gate multi-attach + `set-role` on agent type — reject `--role`/`set-role` for non-hermes.
3. Verify: CLI tests for each path; manual smoke on a hermes instance.

### Phase 3 — Template rewrites
Goal: rendered `.env` and `config.yaml` reflect all attachments.
1. Rewrite `hermes.env.j2` — loop providers, emit per-type keys, "primary wins" on duplicates.
2. Rewrite `hermes-config.yaml.j2` — `model.default`/`model.provider` from primary, `auxiliary.<slot>` per non-primary.
3. Update `playbooks/configure.yaml` to pass `providers` list through.
4. Verify: snapshot tests for representative fixtures; render-locally smoke.

### Phase 4 — Configure stage UX
Goal: `clawctl agent configure <hermes>` walks the user through auxiliary attachments.
1. Add `onboarding.stages.providers.multi: true` to hermes manifest.
2. Extend `_run_providers_stage` to loop offering each of the 9 slots.
3. Run `provider_test` per attachment.
4. Verify: interactive smoke on a real hermes agent; VHS demo for docs.

### Phase 5 — Validate end-to-end + docs
Goal: AC met.
1. Real-environment test: non-DGX host, anthropic primary + DGX-hosted ollama in `compression`; `/health` + compression-path call hits DGX.
2. Update `docs/installation.md` and hermes docs.
3. PR + ATX review + merge.

### Critical path / unknowns

- Before Phase 3: re-verify upstream slot names against `hermes_cli/config.py` at the pinned version — typos in `auxiliary.<slot>` are silent (hermes validates lazily per #501 body).
- Before Phase 5: confirm DGX endpoint reachable from the target hermes host.

## Suggested subtasks

1. Schema migration + `agent.providers` shape extension (Phase 1).
2. CLI surface extension (Phase 2).
3. Configure-stage multi-attach interactive flow (Phase 4).
4. Template rewrites (Phase 3).
5. Tests + docs (cross-phase + Phase 5).

---

<details>
<summary>Prompt Log</summary>

## Planning

**Stage**: plan
**Skill**: /itx:plan-create
**Timestamp**: 2026-05-25T00:00:00Z
**Model**: claude-opus-4-7

```prompt
https://github.com/ric03uec/clawrium/issues/501 plan only first. read the latest command surface area and find wout what needs to be done for this. no file creation or anything. plan only first. find out whats supported for all the tree agent types supported by clawrium
```

**Output**: High-level implementation plan for issue #501. Scoped to hermes-only multi-provider support with primary + 9 auxiliary slot mapping, asymmetric singleton (zeroclaw/openclaw stay singleton), `set-role` as a new hermes-only verb, and `--model` defaulting to the provider's `default_model`. Confirmed upstream slot list and provider→env-var mapping against `NousResearch/hermes-agent@v2026.5.7`.

</details>
