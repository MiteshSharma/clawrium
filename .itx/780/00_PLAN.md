# Issue #780 — Scope clawctl audit to an agent

GitHub: https://github.com/ric03uec/clawrium/issues/780

## Issue Creation

**Stage**: issue-creation
**Skill**: /itx:issue-new
**Timestamp**: 2026-06-21T20:50:00Z
**Model**: claude-opus-4-7

```prompt
update this command (add a new issue first). the audit command needs to be scoped to an agent as part of cli. so the format will also change

[Context: prior turn established that `clawctl audit` has no `agent_name` field in its v1 schema, so `_format_entry` never shows an agent and `--grep <name>` is the only (unreliable) per-agent slice. On follow-up "What should the user be able to do when this is implemented?", user replied: "this should be scoped at agent level. clawctl agent audit <name> or whatever convention".]
```

**Output**: Created issue #780 — "User can run `clawctl agent audit <name>` to view audit history scoped to an agent". Acceptance criteria cover schema additive change, `audit log --agent`, `audit show --agent`, new `clawctl agent audit <name>` subcommand surface, formatter update, stats "By agent" breakdown, and backward-compat tests.
