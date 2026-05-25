# Issue #508 — Bundle 3: clawctl host + agent (Pattern B targets)

Plan delegated to parent issue #435:
[`.itx/435/00_PLAN.md`](../435/00_PLAN.md) §4 (full CLI surface),
§5 (BEFORE→AFTER command map), §6 (output format contract),
§9 (sync redefined), §7 (non-interactive contract).

## Bundle position in stack

| # | Bundle | This one? |
|---|---|---|
| 1 | wolf-i audit-before | done (#506) |
| 2 | clawctl foundation + service/meta | done (#507) |
| 3 | clawctl host + agent (Pattern B) | **YES — largest bundle** |
| 4 | Pattern A attachables + agent sub-resources | no |
| 5 | templates + docs + audit-after | no |

## Branch + PR target

- **Branch:** `feat/435/bundle-3-host-agent` (off `feat/435/bundle-2-foundation`)
- **PR target:** `feat/435-clawctl-ux` (NOT `main`)
- Stacks on top of bundles 1+2.

## Scope of this bundle

- `clawctl host *` Pattern-B verbs (create, get, describe, delete, edit,
  reset, alias, address, label, registry).
- `clawctl agent *` Pattern-B verbs (create, get, describe, delete, edit,
  configure, start, stop, restart, sync, logs, chat, open, port-forward,
  exec, registry).
- Discord/Slack prompts in `agent configure` remain TTY-only fallback for
  this bundle — Bundle 4 (#509) extracts them.
- `clawrium.core.*` untouched (guardrail per plan §2).
