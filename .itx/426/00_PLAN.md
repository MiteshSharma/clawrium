# Issue #426 — Implementation Plan

## Overview

Close the functional gap left by #435/Bundle 4 (#509): the new `clawctl agent
provider attach … --agent …` records desired state in `hosts.json.agents.<n>.providers`,
but no code path materializes that attachment into `hosts.json.agents.<n>.config.provider`,
which is what `sync_agent` actually re-pushes to the remote via Ansible.

Wire `core/lifecycle.sync_agent` to be the reconciliation point: when an
agent has a non-empty `providers` attachment list, look up the provider record
from `~/.config/clawrium/providers.json`, assemble the legacy provider config
shape (the dict `_sync_provider_config` used to write), merge it into the
in-memory `existing_config` before the Ansible push, and — if onboarding state
is still `pending` — advance the state machine through the `providers` stage.

This delivers the customer outcome of #426 ("non-interactive provider config")
through the declarative `attach → sync` flow that #509 set up, without
resurrecting the legacy interactive `_run_providers_stage` code path.

Single-provider invariant per user decision: `attach` hard-fails on a second
attachment. Persistence per user decision: once `config.provider` is written,
it survives subsequent `sync` calls; `detach` does NOT strip it (last-known-good).

## Files to Modify

- `src/clawrium/core/lifecycle.py` — extend `sync_agent` with the
  materialization + state-advance bridge. Single concentrated change between
  the `_resolve_agent_record` block (line ~940) and the existing PENDING-state
  rejection (line ~953).
- `src/clawrium/cli/clawctl/agent/provider.py` — add single-provider guard in
  `attach`. Reject second attachment with a clear error pointing at `detach`.

## Files to Create

- `tests/cli/clawctl/agent/test_sync_materializes_provider.py` — unit coverage
  for the bridge (mocked Ansible). Three cases:
  1. Fresh agent (`providers: ["local-inx"]`, no `config.provider`, state
     `pending`) → `configure_agent` receives `config_data["provider"]["name"]
     == "local-inx"`, state advances past `pending`.
  2. Legacy agent (`config.provider` already set, no `agent.providers` list)
     → bridge is a no-op; `configure_agent` receives the original
     `config_data` unchanged.
  3. Attached provider missing from `providers.json` → sync errors cleanly,
     no partial state advance.
- `tests/cli/clawctl/agent/test_provider_attach_single.py` — assert second
  `attach` to the same agent fails with the documented error.

## Steps

1. **Provider lookup helper** (`lifecycle.py`): import
   `from clawrium.core.providers.storage import get_provider,
   ProvidersFileCorruptedError` near the top, alongside the existing
   `from clawrium.core.providers import …` block at line 1029. Lazy import is
   fine if circulars surface.

2. **Bridge inside `sync_agent`** (`lifecycle.py:901`): immediately after
   `agent_key, agent_type, claw_record = resolved` (line 943) and before the
   state check at line 948, insert:
   - Read `attached = claw_record.get("providers", [])`. If non-empty, take
     `attached[0]` as `provider_name`. (Single-provider invariant is enforced
     at `attach` time; a defensive `len > 1` check here can `LifecycleError`
     with a "data integrity" message in case of manual edits.)
   - Call `provider_record = get_provider(provider_name)`. If `None`, raise
     `LifecycleError(f"attached provider '{provider_name}' not registered;
     clawctl provider registry get")`.
   - Assemble `provider_config` matching the legacy shape from
     `cli/agent.py:360-374`:
     ```python
     provider_config = {
         "name": provider_record.get("name", ""),
         "type": provider_record.get("type", "ollama"),
         "endpoint": provider_record.get("endpoint", ""),
         "default_model": provider_record.get("default_model", ""),
     }
     if provider_record.get("context_window"):
         provider_config["context_window"] = provider_record["context_window"]
     if provider_record.get("max_tokens"):
         provider_config["max_tokens"] = provider_record["max_tokens"]
     ```
   - Read the in-progress `existing_config` (the same dict the existing code
     pulls at line 959) and overlay: `existing_config["provider"] =
     provider_config`. Persistence requirement is met because the
     `updater(h)` closure in `configure_agent` (`lifecycle.py:1709`)
     writes `config_data` back into `hosts.json.agents.<key>.config` after
     Ansible succeeds.

3. **State advancement** (`lifecycle.py`, same block): if `state ==
   OnboardingState.PENDING` and `attached` is non-empty, call
   `complete_stage(hostname, agent_key, "providers", StageStatus.COMPLETE,
   {"provider_id": provider_name})` before the PENDING-rejection check at
   line 953. Re-read state value after the call so the existing check passes.
   - Wrap in `try/except InvalidTransitionError` and downgrade to
     `update_stage_metadata(...)` for the re-sync case (matches legacy
     `_run_providers_stage:498-509`).

4. **PENDING-message refresh** (`lifecycle.py:953-957`): the existing error
   message references `clm agent configure`. With the bridge in place, the
   message should point users at `clawctl agent provider attach <name>
   --agent <agent>` instead. Update the two `LifecycleError` strings at
   lines 954-956 and 962-964.

5. **Single-provider guard** (`cli/clawctl/agent/provider.py:99`): before
   `current.append(name)`, add:
   ```python
   if current and current != [name]:
       emit_error(
           f"agent '{agent}' already has provider {current[0]!r} attached",
           hint=(
               f"detach the current provider first: "
               f"clawctl agent provider detach {current[0]} --agent {agent}"
           ),
       )
   ```
   The `current != [name]` clause preserves the existing idempotent re-attach
   of the same name.

6. **Detach semantics — no-op on `config.provider`**: confirm that
   `cli/clawctl/agent/provider.py:detach` only mutates `agent.providers` and
   leaves `agent.config.provider` alone. Already true by inspection (line
   121-123); add a comment explaining the persistence decision.

7. **Tests** (see Test Strategy).

8. **Update CLAUDE.md / AGENTS.md** — add a one-paragraph note in the
   `Pattern A attachables` section (or wherever Bundle 4 is documented) that
   describes the `attach → sync` reconciliation contract for providers.
   Optional; skip if no such section exists, and instead add a docstring to
   `sync_agent` referencing this issue.

## Test Strategy

### Unit (in CI via `make test`)

Mock Ansible at the `configure_agent` boundary; assert on the `config_data`
dict it receives.

- `test_sync_materializes_attached_provider_into_config` — happy path.
- `test_sync_advances_state_through_providers_when_pending` — state
  transition.
- `test_sync_legacy_agent_without_attachment_unchanged` — regression guard.
- `test_sync_unknown_attached_provider_errors_cleanly` — error path.
- `test_provider_attach_rejects_second_attachment` — single-provider guard.
- `test_provider_attach_same_name_twice_is_idempotent` — preserves existing
  re-attach UX.

### End-to-end (manual, on real host `wolf-i`)

Provider: `local-inx` (ollama, no API key). Agent: fresh hermes named
`test-426-hermes`. Steps and pass criteria documented in the issue body for
reproducibility:

```bash
# clean slate
clawctl agent get | grep test-426 && exit 1

# create — no provider yet
clawctl agent create test-426-hermes --type hermes --host wolf-i --yes
jq '.[] | .agents."test-426-hermes" | {state: .onboarding.state, cfg_provider: .config.provider, providers}' \
  ~/.config/clawrium/hosts.json
# expect: state="pending", cfg_provider=null, providers=null

# attach
clawctl agent provider attach local-inx --agent test-426-hermes
jq '.[] | .agents."test-426-hermes" | {state: .onboarding.state, cfg_provider: .config.provider, providers}' \
  ~/.config/clawrium/hosts.json
# expect: state="pending" (still), cfg_provider=null (still), providers=["local-inx"]

# sync — the bridge fires
clawctl agent sync test-426-hermes
jq '.[] | .agents."test-426-hermes" | {state: .onboarding.state, cfg_provider: .config.provider, providers}' \
  ~/.config/clawrium/hosts.json
# expect: state advanced past "pending", cfg_provider.name == "local-inx",
#         cfg_provider.type == "ollama", endpoint populated

# remote: provider hydrated into the agent's .env
ssh xclm@wolf.tailf7742d.ts.net 'grep -iE "^(provider|ollama|llm_)" ~/.hermes/test-426-hermes/.env'

# remote: hermes unit healthy
ssh xclm@wolf.tailf7742d.ts.net 'systemctl --user is-active hermes-test-426-hermes'

# idempotency: second sync — provider must still be there
clawctl agent sync test-426-hermes
jq '.[] | .agents."test-426-hermes".config.provider.name' ~/.config/clawrium/hosts.json
# expect: "local-inx"

# detach: persistence check — config.provider must NOT vanish
clawctl agent provider detach local-inx --agent test-426-hermes
jq '.[] | .agents."test-426-hermes" | {cfg_provider: .config.provider, providers}' \
  ~/.config/clawrium/hosts.json
# expect: cfg_provider.name still "local-inx", providers=[]

# cleanup
clawctl agent delete test-426-hermes --yes
```

## Risks

- **R1 — Provider record drift between `attach` and `sync`**: user attaches
  `foo`, then mutates `providers.json` to point `foo` at a different
  endpoint, then `sync`. Bridge materializes the *current* `providers.json`
  state at sync time. **Decision: this is correct behaviour** (declarative
  reconcile = current desired state). Document in the `sync_agent` docstring.
- **R2 — Manual hosts.json edit creating `len(agent.providers) > 1`**: the
  defensive check in step 2 catches it. Without that check, sync would pick
  index 0 silently. Keep the explicit `LifecycleError`.
- **R3 — Hermes ollama config shape**: legacy `_sync_provider_config` lived in
  `cli/agent.py` and predates the hermes api_server changes (#346, #476).
  Verify during E2E that the rendered `.env`/`config.toml` on the remote
  contains the expected ollama wiring. If hermes templates expect additional
  keys beyond `{name, type, endpoint, default_model}`, extend the assembled
  dict accordingly.
- **R4 — State machine: `PENDING → providers` transition**: confirmed via
  `core/onboarding.py:279` (`"pending": ["providers"]` in allowed transitions
  table). `complete_stage` will accept the call. The re-sync path
  (state already past `providers`) routes through `update_stage_metadata`
  per legacy precedent.
- **R5 — Multi-provider future**: the design is single-provider by user
  decision. The `agent.providers` field stays a list (don't rename to
  scalar) so a future multi-provider extension doesn't require a hosts.json
  migration — only relaxing the `attach` guard and a fan-out in `sync_agent`.

## Subtasks

None — single task execution. Scope is ~80 LOC across two files plus tests;
all changes share one mental model and one round of E2E.

---

<details>
<summary>Prompt Log</summary>

**Stage**: planning
**Skill**: /itx:plan-create
**Timestamp**: 2026-05-25T00:00:00Z
**Model**: claude-opus-4-7

```prompt
That seems like a bug. In the workflow. So give me a plan to resolve this and test it on a real agent. I need the same workflow where create, attach, and sync works for any provider. This needs to be tested for one provider end to end.

[follow-up resolving open decisions]
For now, single provider is fine. Don't, or fail when multi provider is added.
Provider once added to the agent, is persistent. So however times it syncs, provider should still be there.
Test the provider with local INX. Which is fine.
Use Hermes agent to test. That is also fine.
plan this
```

**Output**: `.itx/426/00_PLAN.md` — single-task plan to bridge
`agent.providers` (attach) → `agent.config.provider` (sync) inside
`core/lifecycle.sync_agent`, with single-provider guard at `attach` time,
detach-preserves-config semantics, and an E2E flow against `wolf-i` using
`local-inx` (ollama) + a fresh hermes agent.

</details>
