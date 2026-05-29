# Issue #541 — Plan

GitHub: https://github.com/ric03uec/clawrium/issues/541

## Bug Creation

**Stage**: bug-creation
**Skill**: /itx:bug-new
**Timestamp**: 2026-05-26T01:30:00Z
**Model**: claude-opus-4-7

```prompt
add a bug for the provider issue. if the provider is valid, user shoudl be able to change provider however many times thy want without getting the gaent to n invalid/pending state.
```

**Output**: Filed issue #541 "User can re-assign an agent's provider any number of times without the agent getting stuck in onboarding state=pending" with labels `type:bug` and `needs-triage`. Bug was discovered while attempting to record `docs/demos/hermes-provisioning.tape` — the demo workflow could not complete end-to-end because `clawctl agent configure --stage providers --provider X` does not transition the onboarding state machine (root cause: `core/onboarding.py:549 run_stage` is a placeholder; v2 CLI at `cli/clawctl/agent/configure.py` never reaches `lifecycle.configure_agent`).
