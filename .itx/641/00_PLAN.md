# Issue #641 — test: sdlc pipeline smoke TC-1

## Outcome
Validate the end-to-end SDLC pipeline (TC-1 through TC-4) runs without manual intervention.

## Approach
- No production code change required — this is a smoke test issue
- Exec should add a single line to `CHANGELOG.md` under `### Internal` (not `### Added`)
- The `### Internal` entry must be removed before any release cut
- PR should pass `make test` and `make lint`

## Files
- `CHANGELOG.md` — add one line under `### Internal` in `[Unreleased]`

## Definition of Done

- [ ] TC-1: clawrium-maurice created issue #641 in `ric03uec/clawrium`
- [ ] TC-2: clawrium-triage applied `planned` + `agent-ready` labels and `.itx/641/00_PLAN.md` is on main
- [ ] TC-3: clawrium-exec opened a PR from branch `exec/641-*` with a passing `make test` + `make lint`
- [ ] TC-4: clawrium-gtm posted an announcement to `#announcements` (Discord channel `1494197384094416906`) — absence of the message is a hard FAIL, not a warning
- [ ] CHANGELOG `### Internal` entry is present on the exec branch and removed before any release cut

## Risk

| Risk | Detection | Mitigation |
|------|-----------|------------|
| Discord message not delivered | Verify message appears in `#announcements` after TC-4; treat absence as FAIL | Check agent logs via `clawctl agent logs clawrium-gtm` if absent |
| Home channel misconfigured | Agent posts `/sethome` prompt instead of announcement | Re-run `clawctl agent configure --stage providers` and restart |
