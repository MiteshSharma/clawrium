# Execution — Issue #533

## Execution

**Stage**: execution
**Skill**: /itx-execute
**Timestamp**: 2026-05-26T06:50:00Z
**Model**: claude-opus-4-7

```prompt
/itx-execute 533

Context: plan at .itx/533/00_PLAN.md. Single task. Grandfather migration —
existing installs keep their current port. ATX via `atx` CLI (up to 3 rounds).
Live verification on wolf-i (hermes/openclaw/zeroclaw). PR base main.
```

**Output**: implementation across `install.py`, `lifecycle.py`, `validation.py`,
`chat_hermes.py`, hermes/openclaw manifests + playbooks + tests. ATX 3 rounds
(rating 3 → 3 → 3-4, no remaining blockers). Live verification on wolf-i:
clawctl-demo (hermes) got api_server.port=8691 (was colliding on 8642 against
espresso); espresso preserved at 8642; chat session succeeded. port-test-oc
(openclaw) and port-test-zc (zeroclaw) installed cleanly with picked gateway
ports in 40000..41999.
