# Issue #380 — Phase 1 Execution Log

Scope (from issue body): `clm skill list` and `clm skill show clawrium/tdd`
return real data from the in-repo catalog; error classes
`MissingRegistryPrefix`, `SkillNotFound`, `ExternalSourceBlocked` exit
non-zero with hints; schema + `parse_skill_ref` + `validate_skill`
(dual-schema dispatch) unit-tested; `make test` + `make lint` green.

Plan reference: `.itx/364/00_PLAN.md` § *Phased execution → Phase 1* and
`.itx/364/02_PHASE0_FINDINGS.md` (which locked the `_meta.yaml` shape
and the source-dirname == registry slug invariant).

## What shipped

**Catalog (repo-root `skills/`, bundled into the wheel as
`clawrium/_skills/` via `pyproject.toml` `force-include`):**

- `skills/README.md` — namespace + slug rules, authoring quickstart.
- `skills/_schema/clawrium.schema.json` — normalized cross-agent schema.
- `skills/_schema/native/{openclaw,hermes,zeroclaw}.schema.json` —
  per-claw native frontmatter schemas, shaped from the upstream
  requirements documented in `.itx/364/02_PHASE0_FINDINGS.md`.
- `skills/clawrium/tdd/{SKILL.md,_meta.yaml}` — first cross-agent skill
  (TDD discipline).
- `skills/{openclaw,hermes,zeroclaw}/README.md` — registry placeholders
  so `clm skill list --registry <claw>` returns an empty list (not
  "registry not found").

**Core (`src/clawrium/core/skills.py`):**

- Error classes: `SkillError` (base), `MissingRegistryPrefix`,
  `InvalidSkillRef`, `ExternalSourceBlocked`, `SkillNotFound`,
  `SchemaValidationError`.
- `parse_skill_ref(raw)` — single chokepoint. Rejection precedence:
  empty → URL/path → bare name (with hint) → unknown registry →
  invalid slug.
- `list_skills([registry])` — enumerates the catalog by registry order;
  rejects unknown registries.
- `load_skill(ref)` — reads `_meta.yaml` (clawrium) or SKILL.md
  frontmatter (native); raises `SkillNotFound` on missing dir/files.
- `validate_skill(skill)` — dual-schema dispatch
  (`clawrium/*` ↔ `_schema/clawrium.schema.json`,
  `<claw>/*` ↔ `_schema/native/<claw>.schema.json`); also enforces the
  `_meta.yaml.name == ref.name` invariant for `clawrium/*`.
- Validator uses `jsonschema.Draft202012Validator` (new runtime dep).

**CLI (`src/clawrium/cli/skill.py` + `src/clawrium/cli/main.py`):**

- `clm skill list [--registry <r>]` — rich table; empty registry gives
  an actionable hint pointing at `skills/<r>/<name>/`.
- `clm skill show <registry>/<name>` — metadata table + rendered
  SKILL.md. Catches every `SkillError` subclass and exits non-zero with
  the matching message.
- Top-level `skill_app` registered alongside `agent`/`host`/`provider`/
  `integration` in `main.py`.

**Tests (46 new, all passing alongside the existing 1947):**

- `tests/test_core_skills.py` — parse/load/validate/list with happy and
  error paths, including dual-schema dispatch against a tmp catalog
  built from the in-repo schemas.
- `tests/test_cli_skill.py` — `clm skill list`/`show` happy path, every
  documented error path, and `--help` surface.

## Verification

```
$ uv run pytest
============================ 2004 passed in 16.31s =============================

$ uv run ruff check src tests
All checks passed!

$ uv run clm skill list
                                 Skills catalog
┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Ref          ┃ Registry ┃ Description                                        ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ clawrium/tdd │ clawrium │ Test-Driven Development discipline. Drives a red → │
│              │          │ green → refactor cycle for...                      │
└──────────────┴──────────┴────────────────────────────────────────────────────┘

$ uv run clm skill show tdd
Error: Skill reference 'tdd' is missing a registry prefix. Use
`<registry>/<name>` (e.g. `clawrium/tdd`). Did you mean: `clawrium/tdd`?
$ echo $?
1
```

## Design notes / non-obvious choices

1. **Catalog is bundled into the wheel** under `clawrium/_skills/` via
   hatch `force-include`, with a dev-mode fallback (`Path(__file__)
   .parents[3] / "skills"`) so source checkouts work without a `pip
   install -e .` round-trip. The package is the source of truth at
   runtime; the repo-root location is purely for ergonomics.
2. **Hand-rolled validator avoided** in favor of pulling in
   `jsonschema>=4.0.0` (one new runtime dep). Rationale: the same
   schemas will be used by `scripts/validate_skills.py` in Phase 6;
   maintaining two implementations would risk divergence.
3. **Bare-name hint is best-effort and degrades silently** on catalog
   read failures, so a missing catalog never masks the underlying
   "you forgot the registry prefix" user error.
4. **`_short_description` swallows per-skill errors** in `clm skill list`
   to keep the table rendering robust against one bad skill. The full
   error surfaces via `clm skill show <ref>`.
5. **Slug invariant** (`_meta.yaml.name == directory name`) is enforced
   in `validate_skill` rather than `load_skill` so the loader stays
   honest about what's on disk; validation is the gate. Required for
   the zeroclaw remove semantics documented in
   `.itx/364/02_PHASE0_FINDINGS.md`.

## What this PR does not do

Per the issue scope, this PR explicitly stops at *browsing*. Per-agent
install/list/remove (`clm agent skill *`), desired-state files, and the
per-claw `skills_apply.yaml` playbooks land in Phases 2–3 (issues
#381, #382). GUI parity lands in Phase 4 (#383).

## ATX Review iterations

| Review | Rating | Blockers | Status | Cost | Time |
|--------|--------|---------|--------|------|------|
| 1 | 2/5 | B1–B6 | All fixed (B2 was a false positive) | $4.30 | 12m23s |
| 2 | 3/5 | B6 | Test was vacuous — fixed with mocked Draft202012Validator and mixed-type-path inputs | $3.64 | 7m59s |
| 3 | 4/5 | None | Merge gate passed | $2.01 | 6m36s |

Carried to follow-up issues (out of Phase 1 scope):
- W-new1 (CliRunner `mix_stderr` ergonomics) — repo-wide CLI test pass.
- W1 (slug invariant extension to native registries) — Phase 2.
- W2 / W12 / W13 / W14 (additionalProperties lockdown + SKILL.md bidi
  sanitization) — Phase 3, before any community-contributed catalog
  source is added.

Co-Authored-By: @atx-ci <269048218+atx-ci@users.noreply.github.com>

---

<details>
<summary>Prompt Log</summary>

**Stage**: execution
**Skill**: /itx:execute
**Timestamp**: 2026-05-17T00:00:00Z
**Model**: claude-opus-4-7

```prompt
/itx-execute 380 --pr-base=issue-386-phase0-research
```

</details>
