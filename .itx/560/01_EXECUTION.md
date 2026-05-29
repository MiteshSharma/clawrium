## Phase 1 — Drop `--canonical` flag

**Stage**: execute-phase-1
**Skill**: /itx:execute (manual invocation)
**Timestamp**: 2026-05-29T00:00:00Z
**Model**: claude-opus-4-7

```prompt
Execute Phase 1 of issue #560 in this worktree.

Scope:
- src/clawrium/cli/clawctl/agent/sync.py: remove --canonical and --force typer Options; delete the if canonical / else branch; canonical pipeline becomes unconditional default.
- src/clawrium/core/lifecycle.py:1718-1790: delete the legacy Discord/Slack hydration block (the conditional reading agent_record.config.channels.discord).
- src/clawrium/core/lifecycle.py: grep + delete any other dead code under configure_agent reachable only from the legacy sync path.
- tests/cli/clawctl/agent/test_sync*.py and related: drop --canonical from test invocations; rewrite tests that exercised the legacy path to assert canonical-as-default.
```

**Output**:
- `src/clawrium/cli/clawctl/agent/sync.py`: removed `--canonical` and `--force` Options; removed `sync_agent` / `resolve_lifecycle_backend` imports; canonical pipeline (`sync_agent_canonical`) is now the unconditional default. Legacy ansible `sync_fn` fork deleted.
- `tests/cli/clawctl/agent/test_multi_instance_resolution.py`: rewrote `test_sync_passes_instance_name_not_type` to patch `sync_agent_canonical` and assert the on-host instance name is the first positional arg.
- `tests/cli/clawctl/agent/test_sync_diff.py`: rewrote `test_diff_text_does_not_invoke_real_sync` to assert `sync_agent_canonical` is not invoked under `--diff`.
- `src/clawrium/core/lifecycle.py:1718-1790` (Discord/Slack hydration in `configure_agent`): **NOT deleted in this PR.** `configure_agent` is still called by `start_agent` (lifecycle.py:594) and the `clawctl agent configure` CLI command, both of which are out of Phase 1 / out of #560 scope per the plan. Deleting the hydration would change behavior for those flows. Tracked as TODO-FOLLOWUP Callout on PR; deferred decision (rename helper vs. fold into F3 inputs) belongs in a separate change.

Tests at baseline (45 pre-existing zeroclaw failures unrelated to this PR remain; no new regressions). Lint clean.
