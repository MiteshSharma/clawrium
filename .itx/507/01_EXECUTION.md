# Issue #507 — Bundle 2: clawctl foundation + service/meta commands

GitHub: https://github.com/ric03uec/clawrium/issues/507

Parent: #435 — clawctl kubectl-style UX

---

## Execution

**Stage**: execution
**Skill**: /itx:execute
**Timestamp**: 2026-05-24T03:30:00Z
**Model**: claude-opus-4-7

```prompt
/itx:execute 507 --pr-base=feat/435-clawctl-ux
```

**Output**: Bundle 2 foundation landed:

1. `pyproject.toml` — `[project.scripts]` renamed from `clm = "clawrium.cli.main:app"` to `clawctl = "clawrium.cli:app"`. Clean break, no alias.
2. `src/clawrium/cli/__init__.py` — new top-level `clawctl` Typer app. Registers `service`, `version`, `completion`, `tui`, `gui`, `host`, `agent`, `provider`, `channel`, `integration`, `skill`, `mcp` (plan §4 surface complete; closes Risk R2).
3. `src/clawrium/cli/output/{table,json_yaml,stream,errors,age,status}.py` — shared rendering primitives implementing the plan §6 output contract.
4. `src/clawrium/cli/service.py` — `service init` (delegates to existing init), `service start|stop|snapshot` (placeholder stubs).
5. `src/clawrium/cli/meta.py` — `version` + `completion <bash|zsh|fish>` (uses Click's `shell_completion`).
6. `src/clawrium/cli/clawctl/{host,agent,provider,channel,integration,skill,mcp}.py` — stub group apps. Each verb prints `Not implemented: <group> <verb>` exit 0. Living under a sub-package avoids name collisions with legacy `cli/host.py`, `cli/agent.py` etc. that still serve the `clm` test surface.
7. `tests/cli/output/` + `tests/cli/test_service.py` + `tests/cli/test_meta.py` + `tests/cli/test_app.py` — 82 new tests covering the plan §"Specific Outcomes to Validate" assertions.

Verification: `uv run pytest -q` → 2660 passed, 6 skipped (was 2578 + 6). `uv run ruff check src tests` → all checks passed. Legacy `clm` Typer app at `clawrium.cli.main:app` unchanged; legacy tests continue to pass.

`make format` was NOT run repo-wide — it would reformat ~66 unrelated files (pre-existing drift), violating the `clawrium.core.*` untouched guardrail. Only the new files (already ruff-format-clean) are touched.
