# Plan — Issue #533

**Title**: Run any number of agents of any type on a host without port collisions
**URL**: https://github.com/ric03uec/clawrium/issues/533
**Labels**: type:bug, needs-triage

## Overview

Every per-agent network listener should pick its port the same way `hermes dashboard_port` already does in `install.py:574-615`: per-instance from a dedicated range, collision-checked against other agents on the host, preserved across reinstalls. Today three listeners exist; only one follows this pattern.

| Listener | Current | Target |
|---|---|---|
| `hermes dashboard` | per-instance `45000+md5%2000`, collision walk, preserve | ✅ no change |
| `hermes api_server` | literal `8642` everywhere | per-instance `8600+md5%100`, collision walk, preserve |
| `openclaw / zeroclaw gateway` | `40000+md5%2000`, no collision check, no preserve | add collision walk + preserve; keep range |

**Migration policy**: grandfather. On reinstall, if a port is already persisted in `hosts.json`, keep it. New installs get a freshly-picked port. Existing in-use agents (espresso, maurice, zeroclaw fleet) are not restarted.

**Subtasks**: None — single task execution. The two listener families (hermes api_server, openclaw/zeroclaw gateway) share the same pattern and the same one helper.

## Approach

Extract a shared helper `_pick_per_instance_port(host, agent_name, base, span, port_field_path)` that:
1. Reads the persisted port at `port_field_path` from the agent record (returns it if present — preservation).
2. Otherwise computes a hash-based candidate (`base + md5(agent_name) % span`).
3. Walks +1 (wrapping in `[base, base+span)`) past any port already in use by other agents on the host.
4. Raises `InstallationError` with a clear message if all `span` slots are full.

Apply it three places: hermes dashboard (refactor existing inline block), hermes api_server (new), openclaw/zeroclaw gateway (new). One helper, three callers, one canonical pattern.

## Files to Modify

| File | Change |
|---|---|
| `src/clawrium/core/install.py:563-615` | Extract `_pick_per_instance_port()` helper from the current dashboard-port block. Call it for: (a) openclaw/zeroclaw gateway (replaces `40000 + port_hash % 2000` at line 566, adds collision walk + preservation), (b) hermes dashboard (refactor existing into the helper), (c) hermes api_server (new, range `8600..8699`). |
| `src/clawrium/core/install.py:674,1007` | Replace literal `"port": 8642` with the assigned `api_server_port`. |
| `src/clawrium/core/lifecycle.py:1361-1375` | Replace literal `"port": 8642` (line 1371) in the legacy-shape reconstruction path. Read from `agent_record.config.api_server.port` if present; only fall back to assigning a new port (via the helper) if the field is missing — and persist that back. |
| `src/clawrium/core/validation.py:887-1006` | `validate_hermes_health()` reads the port from the agent record. Update docstring example and the `curl -fsS http://127.0.0.1:<port>/health` line. |
| `src/clawrium/core/chat_hermes.py:43` | Update docstring example URL (chat already reads the port from the agent record). |
| `src/clawrium/platform/registry/hermes/templates/hermes.env.j2:43` | No change required (already uses `config.api_server.port \| default(8642)`). Optionally tighten the default to a sentinel that would obviously fail rather than the legacy literal. |
| `src/clawrium/platform/registry/hermes/playbooks/configure.yaml:428,441-442` | No change required (already templatized). |
| `src/clawrium/platform/registry/hermes/manifest.yaml:63,65,96,135` | Update onboarding `message:` strings and the `validate.command` curl probe — no longer reference "8642"; either templatize or use generic wording. |
| `src/clawrium/platform/registry/openclaw/playbooks/install.yaml:145` | Replace `openclaw_port: "{{ 40000 + ((agent_name \| hash('md5') \| int(base=16)) % 2000) }}"` with `openclaw_port: "{{ config.gateway.port }}"`. `install.py` becomes the source of truth; the playbook reads from inventory vars (which `zeroclaw/configure.yaml:8` already does for `gateway_port`). |
| `tests/test_install_ports.py` (new) | (1) Two hermes installs on same host → distinct api_server ports. (2) Reinstall preserves the api_server port. (3) Hash-colliding openclaw/zeroclaw names on same host → distinct gateway ports. (4) Port-pool exhaustion → `InstallationError` with helpful message. |
| `tests/test_validation_hermes.py` (existing or new) | `validate_hermes_health()` builds the curl URL from the agent's persisted port, not 8642. |

## Steps

1. Extract `_pick_per_instance_port()` helper in `install.py`. Refactor the existing dashboard-port block to call it. **Run `make test`** — should be green (pure refactor, behavior unchanged).
2. Apply helper to openclaw/zeroclaw gateway port assignment; persist `config.gateway.port` on first install + preserve on reinstall.
3. Update `openclaw/playbooks/install.yaml:145` to read `config.gateway.port` from inventory instead of recomputing.
4. **Run `make test`** — openclaw/zeroclaw paths still green.
5. Apply helper to hermes `api_server` port (range `8600..8699`). Persist `config.api_server.port`.
6. Update `install.py:674,1007` and `lifecycle.py:1371` to use the assigned port.
7. Update `validation.py`, `chat_hermes.py` docstring, `manifest.yaml` messages.
8. Add new tests in `tests/test_install_ports.py`. Update existing validation tests.
9. **Run `make test` + `make lint`** — full green.
10. Manual verification on `wolf-i`: delete the broken `clawctl-demo`, recreate, attach `dgx-spark`, sync, chat. Confirm a port other than 8642 is assigned and chat works while espresso is still on 8642.

## Test Strategy

- **Unit**: new `tests/test_install_ports.py` covering the helper directly + integration through install. ~80 LOC of tests.
- **Validation**: extend `test_validation_hermes.py` to assert the templatized port appears in the rendered curl command.
- **Manual end-to-end**: `clawctl-demo` on `wolf-i` becomes the live regression case. Demo recording (`/create-vhs`) is the downstream verification.
- **Regression**: `make test` full suite + `make lint`.

## Risks

- **Legacy-shape reconstruction in `lifecycle.py:1371`** — hit only on corrupt/legacy `hosts.json`. Decision: if no port persisted, assign one via the helper and persist back so subsequent runs are stable. Document in the comment.
- **Manifest `validate.command:135`** — `curl -fsS http://0.0.0.0:8642/health` runs during install validation. Options: templatize via Ansible vars at validate time, or drop the literal port check in favor of the configure-time health probe (which is already templatized). Lean toward templatize since the manifest already supports Jinja in some fields.
- **Playbook coupling** — `openclaw/install.yaml:145` currently recomputes the port from `agent_name`. After this PR, `install.py` is the source of truth. Safe because clawctl re-syncs the playbook on each install; no cached-playbook-on-remote concern.
- **Existing in-use agents** — espresso/maurice stay on 8642 (grandfathered). Two hermes on the same host today would already be broken; users hitting that need to delete + reinstall the conflicting agent. PR description must call this out.

## ATX Review

`mcp.review_enabled: true` per `.claude/itx-config.json` — request review via `mcp__atx__request_review` before commit. Iterate until rating > 3/5 with no blocking issues. Expected review topics: port-range choice (8600..8699 — only 100 slots, vs dashboard's 2000), helper signature, manifest-validate templating choice, migration documentation.

## Estimated Size

~120 LOC implementation + ~120 LOC tests across 8 files. Complexity:S.

---

## Prompt Log

### Bug Creation

**Stage**: bug-creation
**Skill**: /itx:bug-new
**Timestamp**: 2026-05-26T05:50:00Z
**Model**: claude-opus-4-7

```prompt
hermes api_server port is hardcoded to 8642 in install.py/lifecycle.py/validation.py/templates,
causing TCP bind collisions when running multiple hermes instances on the same host.
Discovered while recording a demo: clawctl-demo on wolf-i (host already running espresso on 8642)
ended up with chat returning "Authentication failed: Hermes rejected Bearer ***" because SSH
tunnel to wolf-i:8642 hits espresso's daemon, which rejects clawctl-demo's bearer.

User clarification: each agent of any type needs to have a randomly selected port — scope
broadened beyond hermes to cover openclaw/zeroclaw gateway port too.
```

**Output**: GitHub issue #533.

### Planning

**Stage**: planning
**Skill**: /itx:plan-create
**Timestamp**: 2026-05-26T06:05:00Z
**Model**: claude-opus-4-7

```prompt
/itx-plan-create 533
```

**Output**: this plan; no subtasks (single-task execution); label transition to `planned`.
