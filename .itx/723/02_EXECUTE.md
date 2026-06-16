# Execution log — #723

feat(openclaw): accept litellm provider type (extend support set + JSON render)

## Implementation

Three contained edits in `src/clawrium/core/render.py`:

1. **Allow-list bump** — added `litellm` to both
   `_AGENT_TYPE_PROVIDER_SUPPORT['openclaw']` and
   `_OPENCLAW_SUPPORTED_PROVIDERS`. Narrowed the deferred-work comment
   to zeroclaw only (zeroclaw still has no `models.providers.<id>`
   writer; tracked separately).
2. **`_render_openclaw_json` refactor** — signature now accepts the
   full `ProviderInputs` (was: just the prefixed model id). Single call
   site updated. Docstring documents the new 6th managed path.
3. **`models.providers.<provider-name>` writer** — when `provider.type
   == "litellm"`, the renderer writes a custom-provider block matching
   upstream openclaw's shape (`api: "openai-completions"`, `baseUrl`
   normalized to `<endpoint>/v1`, inline `apiKey`, one `models[]` entry
   built from `default_model` with `contextWindow: 65536`, `maxTokens:
   16384` matching the gtm vLLM config). The model-id prefix for
   litellm is the clawctl provider name (`<provider-name>/<model>`),
   not a static type-keyed string.

Tests added:
- `tests/core/test_render.py`:
  - `litellm` added to `test_renderer_is_idempotent` parametrize.
  - `_OPENCLAW_ENV_LITELLM` byte-lock + parametrize entry — pins that
    the env body is identical to the openclaw + ollama baseline modulo
    the model id (no `LITELLM_*` env var emitted).
  - `test_openclaw_litellm_env_has_no_litellm_specific_vars` — pins
    that the bearer never lands in the env file (different blast radius
    than `openclaw.json`).
  - `test_openclaw_litellm_writes_models_providers_block` — full shape
    assertion against the upstream openclaw docs.
  - `test_openclaw_litellm_baseurl_with_v1_suffix_not_double_appended`
    — `/v1` normalization invariant.
  - `test_openclaw_non_litellm_does_not_emit_models_block` — only
    litellm writes `models.providers`; a stray block would shadow the
    daemon's built-in provider table.
  - `test_openclaw_litellm_preserves_unmanaged_baseline_keys` — pins
    that adding `models` doesn't perturb other baseline keys.
- `tests/cli/clawctl/provider/test_agent_attach_openclaw_litellm.py` (new):
  - `test_attach_litellm_to_openclaw_succeeds` — CLI-facing happy path.
  - `test_openclaw_single_provider_invariant_still_holds_for_litellm`
    — #426 invariant preserved across the allow-list change.
  - `test_openclaw_litellm_passes_build_render_inputs` — end-to-end
    assembly-layer signal.

Docs + changelog:
- `docs/agent-support/openclaw.md` and mirrored
  `website/docs/agent-support/openclaw.md` — added a LiteLLM / vLLM /
  custom OpenAI-compatible proxy row.
- `CHANGELOG.md` — `[Unreleased]` → `### Added` entry citing the new
  capability and the rendered shape.

Existing byte-lock fixtures for openclaw + openrouter, anthropic,
openai, bedrock, ollama, zai pass unchanged — the
`_render_openclaw_json` signature change is non-behavioral for those
types.

## Verification

### Local

```
$ make test-py
3412 passed, 2 skipped in 33.80s

$ make lint-py
All checks passed!
```

### Live on wolf-i (openclaw, x86_64, `wolf.tailf7742d.ts.net`)

Pre-state snapshot saved to `.itx/723/snapshots/hosts.json.pre`.

```
$ uv run clawctl agent provider detach clawrium-bedrock --agent wolf-i
agent/wolf-i: detached provider 'clawrium-bedrock'

$ uv run clawctl agent provider attach clawrium-gtm-litellm --agent wolf-i
agent/wolf-i: attached provider 'clawrium-gtm-litellm'

$ uv run clawctl agent sync wolf-i
agent/wolf-i: validate: assembling render inputs for wolf-i
agent/wolf-i: render: rendering canonical config for openclaw
agent/wolf-i: diff: reading on-host files from wolf.tailf7742d.ts.net
agent/wolf-i: write: writing /home/wolf-i/.openclaw/env
agent/wolf-i: write: writing /home/wolf-i/.openclaw/openclaw.json
agent/wolf-i: restart: restarting openclaw-wolf-i.service
agent/wolf-i: verify: checking unit is active
agent/wolf-i: synced  (drift=0, took 1s, 2 written, 0 unchanged)

$ uv run clawctl agent sync wolf-i      # idempotent: second sync touches nothing
agent/wolf-i: synced  (drift=0, took 0s, 0 written, 2 unchanged)

$ uv run clawctl agent exec wolf-i -- --version
OpenClaw 2026.3.13 (61d171a)
```

### On-host config visible via openclaw's own readout

```
$ uv run clawctl agent exec wolf-i -- models
Config        : ~/.openclaw/openclaw.json
Default       : clawrium-gtm-litellm/writer
Providers w/ OAuth/tokens (0): -
- clawrium-gtm-litellm effective=models.json:sk-99f4a...eabd6308 \
    | models.json=sk-99f4a...eabd6308 \
    | source=models.json: ~/.openclaw/agents/main/agent/models.json
```

Confirms:
- `agents.defaults.model.primary` == `clawrium-gtm-litellm/writer` (the
  per-attachment prefix in #723).
- `models.providers.clawrium-gtm-litellm.apiKey` is the LiteLLM master
  key (`sk-99f4a...eabd6308` matches the secret in `secrets.json`),
  visible to the daemon's effective-auth store.

### Smoke chat end-to-end

```
$ uv run clawctl agent exec wolf-i -- agent --agent main \
    --message "Reply with exactly one word: pong"
pong
```

Traffic flow:
`clawctl` → openclaw gateway on `wolf.tailf7742d.ts.net:40198` →
`models.providers.clawrium-gtm-litellm` (api: openai-completions, baseUrl
`http://192.168.1.17:4000/v1`) → LiteLLM proxy → vLLM at `inx` running
`Qwen3-Next-80B-A3B-Instruct-FP8`.

Single-token reply (`pong`) confirms the full path works. The "gateway
closed (1000 normal closure) … falling back to embedded" notice is
openclaw's standard behavior for one-shot `agent --message` calls —
not a regression introduced by this PR (the same notice appeared
pre-change against bedrock).

## Rollback (if needed)

```
$ uv run clawctl agent provider detach clawrium-gtm-litellm --agent wolf-i
$ uv run clawctl agent provider attach clawrium-bedrock --agent wolf-i
$ uv run clawctl agent sync wolf-i
```

Pre-state snapshot at `.itx/723/snapshots/hosts.json.pre` for
deterministic restore if `provider attach` ever takes a non-default
path.

## Prompt log

### Execution

**Stage**: execution
**Skill**: /itx-execute
**Timestamp**: 2026-06-15T21:45:00-07:00
**Model**: claude-opus-4-7

```prompt
/itx-execute 723
```

**Output**: Render-layer changes landed on `feat/723-openclaw-litellm`
(this branch) per `.itx/723/00_PLAN.md`. Unit + CLI tests added (10
new). `make test-py` + `make lint-py` green. Live verification on
wolf-i: provider swap + sync clean (drift=0, idempotent), models
readout confirms the new `models.providers` block, single-token smoke
chat through openclaw → LiteLLM → Qwen3-Next backbone on inx returned
`pong`.
