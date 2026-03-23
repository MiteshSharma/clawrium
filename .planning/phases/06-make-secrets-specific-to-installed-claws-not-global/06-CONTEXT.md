# Phase 6: Make Secrets Specific to Installed Claws - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor secrets from global scope to per-claw-instance scope. Each installed claw instance has its own set of secrets identified by claw name. Breaking change from Phase 5's global secrets.json format.

</domain>

<decisions>
## Implementation Decisions

### Scoping Model
- **D-01:** Per claw instance — each installed claw has its own secrets
- **D-02:** Instance identity is `host:claw_type:claw_name` internally (all three always present during install)
- **D-03:** CLI uses claw name only — assumes claw names are unique across hosts
- **D-04:** Same secret key can have different values per instance (e.g., OPENAI_API_KEY differs between claws)
- **D-05:** No templates — each instance sets secrets from scratch
- **D-06:** Clean break from global — old global secrets.json deleted, no migration path

### Storage Structure
- **D-07:** Nested JSON in single secrets.json file — reuses existing file locking pattern
- **D-08:** Top-level keys are colon-separated: `{ "wolf:openclaw:work": { "OPENAI_API_KEY": {...} } }`
- **D-09:** Clean break — no version field or backward compatibility code

### CLI Command Changes
- **D-10:** `clm secret set <clawname> KEY` — claw name is first positional, then key name
- **D-11:** Secrets can only be set for installed/initialized claws
- **D-12:** `clm secret list` shows all claws grouped, with their secrets and missing required secrets per claw
- **D-13:** Claw identified by name only (e.g., `oc-work`) — must be unique across fleet

### Install Flow Changes
- **D-14:** Install succeeds without secrets — secrets are set post-install via `clm secret set`
- **D-15:** `clm status` shows claws with missing secrets as 'degraded' state with message listing missing keys
- **D-16:** Secret changes require manual resync via `clm install --sync <clawname>` to apply
- **D-17:** Manifest validation at install — checks required_secrets schema is valid, fails fast if malformed

### Claude's Discretion
- Exact JSON schema field names and nesting structure
- Error messages and help text wording
- Internal function signatures and module organization
- Test fixture structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Code
- `src/clawrium/core/secrets.py` — Current global secrets implementation to refactor
- `src/clawrium/cli/secret.py` — Current CLI commands to modify
- `src/clawrium/core/hosts.py` — fcntl file locking pattern to reuse
- `src/clawrium/core/install.py` — Install flow to extend with degraded state handling
- `src/clawrium/cli/status.py` — Status display to extend with degraded state

### Prior Context
- `.planning/phases/05-secrets-management/05-CONTEXT.md` — Original secrets decisions (D-01 through D-17)
- `.planning/phases/04-installation-fleet-status/04-CONTEXT.md` — Install flow patterns

### Requirements
- `.planning/REQUIREMENTS.md` — SEC-01, SEC-02, SEC-03 (still apply, now per-instance)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/secrets.py`: SecretEntry TypedDict, fcntl locking, atomic JSON writes — all reusable with modified key structure
- `cli/secret.py`: Rich tables, getpass masked input, typer.confirm — all reusable
- `core/health.py`: Health check patterns to extend for degraded state

### Established Patterns
- Typer positional arguments for target identification
- JSON for user data storage
- fcntl advisory locking for file safety
- Rich tables for structured CLI output

### Integration Points
- Modify `core/secrets.py` — change from flat dict to nested by instance
- Modify `cli/secret.py` — add clawname positional argument
- Extend `cli/status.py` — add degraded state display
- Add `--sync` flag to `cli/install.py`

</code_context>

<specifics>
## Specific Ideas

- Claw name uniqueness enforced during install — error if name already exists in fleet
- `clm secret list` output groups by claw, shows installed host, lists secrets and gaps
- Degraded state in status: "degraded (missing: OPENAI_API_KEY, ANTHROPIC_API_KEY)"
- Internal key format: `{host}:{claw_type}:{claw_name}` stored in secrets.json

</specifics>

<deferred>
## Deferred Ideas

- Encryption at rest — adds key management complexity, defer to v2
- `clm claw sync` as dedicated command — using `clm install --sync` for now
- Per-host or per-claw-type scoping — per-instance is sufficient
- Secret templates or copy-from — users can script if needed
- Auto-restart on secret change — manual sync for v1

</deferred>

---

*Phase: 06-make-secrets-specific-to-installed-claws-not-global*
*Context gathered: 2026-03-22*
