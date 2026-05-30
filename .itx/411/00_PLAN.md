# Issue #411 — Allow adding ad-hoc skills to agents

## Overview

Today the only way to land a skill on a clawrium-managed agent is to ship it
in-repo under one of four hard-wired registries (`clawrium/`, `openclaw/`,
`hermes/`, `zeroclaw/`) and let `clm agent skill attach` install it. Users
need to author **ad-hoc skills** for their own workflows without sending a PR
against the clawrium repo.

This issue replaces the four-registry catalog with a two-source unified
catalog:

```
vetted/<name>      ← in-repo, gated by PR review, ships in the wheel
local/<name>       ← user-owned, stored at ~/.config/clawrium/skills/
```

Both sources use a single canonical file format that follows the
[agentskills.io](https://agentskills.io) standard (YAML frontmatter +
markdown body in `SKILL.md`). Translation to per-claw native frontmatter
happens inside `materialize_for_claw` and is invisible to the user — the
"value prop" the issue calls out.

To bound the blast radius for v1, the per-claw support table starts with
**hermes only**. Openclaw and zeroclaw are wired off behind a hardcoded
table and re-enabled in follow-up issues once their materializers are
re-tested end-to-end.

## Target model

```
                      ┌─────────────────────────────────┐
                      │     Unified Skill Catalog       │
                      │  (agentskills.io standard fmt)  │
                      └────────────┬────────────────────┘
                                   │
            ┌──────────────────────┴──────────────────────┐
            ▼                                             ▼
   Vetted (in-repo)                              Local (user-owned)
   skills/vetted/<name>/SKILL.md          ~/.config/clawrium/skills/<name>/SKILL.md
   gated via PR review                    created by `clm skill add` or GUI
            │                                             │
            └──────────────────────┬──────────────────────┘
                                   ▼
                   clm agent skill attach <ref> --agent <a>
                                   │
                                   ▼
          materializer renders per-claw SKILL.md → host (existing pipeline)
```

## Decisions (locked)

1. **Reference grammar**: `<source>/<name>` where `source ∈ {vetted, local}`.
   Bare names rejected with `MissingSourcePrefix`.
2. **Name is the global unique key**: cannot have `vetted/tdd` *and*
   `local/tdd`. Create rejects with `SkillNameConflict`.
3. **Name is immutable**: `clm skill edit` and the GUI edit form cannot
   change `name`. Renaming = delete + re-create.
4. **Format**: agentskills.io standard `SKILL.md` with YAML frontmatter.
   `_meta.yaml` is dropped. Required fields: `name`, `description`.
   Optional: `version`, `license`, `author`, `tags`, `platforms`,
   `prerequisites`.
5. **Vetted source is read-only** at runtime. `clm skill edit/remove` on a
   `vetted/*` ref → `ReadOnlySource`.
6. **Per-claw support is hardcoded and global**, not per-skill:

   ```python
   # core/skills.py
   SUPPORTED_CLAWS_BY_DEFAULT: dict[str, bool] = {
       "hermes":   True,
       "openclaw": False,
       "zeroclaw": False,
   }
   ```

   `materialize_for_claw` and `clm agent skill attach` consult this table
   and raise `ClawNotSupported` for any `False` claw. Openclaw and zeroclaw
   get flipped on in follow-up issues once their materializers + e2e tests
   are wired.
7. **Existing skills migrate to `vetted/`**: the 6 working skills
   (`clawrium/tdd`, `hermes/blog-author`, `hermes/daily-digest`,
   `hermes/docs-sync`, `hermes/issue-triage`, `hermes/release-watcher`) are
   re-authored into the new flat format and moved to `skills/vetted/`.
   `skills/openclaw/` and `skills/zeroclaw/` are deleted (placeholder
   READMEs only).
8. **Desired-state migration is one-shot**: on first read after upgrade,
   `read_state` rewrites legacy refs (`clawrium/tdd` → `vetted/tdd`,
   `hermes/blog-author` → `vetted/blog-author`, etc.) and drops anything it
   doesn't recognise with a warn-log.

## Files to modify / create

### Catalog & schema

- **delete** `skills/clawrium/`, `skills/openclaw/`, `skills/hermes/`,
  `skills/zeroclaw/`
- **delete** `skills/_schema/clawrium.schema.json`, `skills/_schema/native/`
- **create** `skills/_schema/agent-skill.schema.json` — agentskills.io
  standard
- **create** `skills/vetted/<name>/SKILL.md` for: `tdd`, `blog-author`,
  `daily-digest`, `docs-sync`, `issue-triage`, `release-watcher`
- **modify** `skills/README.md` — rewrite for two-source model

### Core

- **modify** `src/clawrium/core/skills.py`
  - Rename `REGISTRIES` → `SOURCES = ("vetted", "local")`
  - Delete `NATIVE_REGISTRIES`, `IncompatibleSkillRegistry`
  - Rename `MissingRegistryPrefix` → `MissingSourcePrefix`
  - Add `SkillNameConflict`, `SkillNameImmutable`, `ReadOnlySource`,
    `ClawNotSupported`
  - Add `SUPPORTED_CLAWS_BY_DEFAULT` (hermes=True, others=False)
  - Rewrite `parse_skill_ref` for the new grammar
  - Add `_local_catalog_root()` returning XDG path
  - Rewrite `list_skills` / `load_skill` to union both sources and enforce
    global name uniqueness at load time
  - Refactor `materialize_for_claw` to consume the flat agentskills format
    and dispatch through a hardcoded per-claw mapping table, gated on
    `SUPPORTED_CLAWS_BY_DEFAULT`
- **modify** `src/clawrium/core/skills_apply.py`
  - Drop registry/incompat plumbing
  - Gate dispatch on `SUPPORTED_CLAWS_BY_DEFAULT[claw]` and skill
    `prerequisites`
- **create** `src/clawrium/core/skills_local.py`
  - `create_local_skill(name, frontmatter, body) -> SkillRef`
  - `update_local_skill(name, frontmatter, body)` (rejects `name` mutation)
  - `delete_local_skill(name)`
  - All with schema validation, conflict detection, atomic file writes
- **modify** `src/clawrium/core/skills_state.py`
  - One-shot legacy ref migration on `read_state`

### CLI

- **modify** `src/clawrium/cli/skill.py`
  - Add `add`, `edit`, `remove`
  - Simplify `list` (new `Source` + `Supported on` columns)
  - Extend `show` (source badge, supported-claws line)
  - Drop `--registry` flag
- **modify** `src/clawrium/cli/agent_skill.py`
  - Parse new refs
  - Drop `IncompatibleSkillRegistry` branches
  - Surface `ClawNotSupported` cleanly on attach

### GUI backend

- **modify** `src/clawrium/gui/routes/skills.py`
  - List endpoint returns unioned catalog with `source` and `supported_on`
  - Add `POST /api/skills`, `PUT /api/skills/{name}`,
    `DELETE /api/skills/{name}` — vetted is read-only; `name` cannot change
    on PUT

### GUI frontend

- **modify** `gui/src/app/skills/page.tsx`
  - Drop `REGISTRY_LABELS`, tab bar, `activeRegistry` state
  - Render single flat list
  - Add **+ Create Skill** button → modal
  - Each card shows source badge + per-claw support badges
- **create** `gui/src/components/skills/skill-create-form.tsx`
  - Controlled form for required/optional fields + body textarea
  - Client-side validation; surfaces 422s from server
- **modify** `gui/src/components/skills/skill-card.tsx`
  - Source badge, supported-claw badges
  - Edit/delete actions gated on `source==='local'`
- **modify** `gui/src/components/skills/skill-detail.tsx`
  - Supported-claws line
  - `name` field read-only in edit mode
- **create** `gui/src/hooks/use-create-skill.ts`,
  `use-update-skill.ts`, `use-delete-skill.ts`
- **modify** `gui/src/lib/types.ts`
  - Replace `SkillRegistry` union with `SkillSource = 'vetted' | 'local'`
  - Add `supported_on: Record<ClawType, boolean>`

### Slash command

- **create** `.claude/commands/skill-create.md`
  - Short prompt: ask user for required fields, draft an
    agentskills-format `SKILL.md`, run `clm skill add local/<name>
    --from <tmpfile>`

### Packaging

- **modify** `pyproject.toml`
  - Update `force-include` to bundle `skills/vetted/` into the wheel as
    `clawrium/_skills/vetted/`

### Tests

- **rewrite** `tests/core/test_skills*.py`, `tests/cli/test_skill*.py`,
  `gui/src/components/skills/*.test.tsx`, GUI route tests, for:
  - new ref grammar
  - single unioned list shape
  - global name uniqueness
  - name immutability on edit
  - vetted read-only
  - `ClawNotSupported` for openclaw/zeroclaw
  - create/edit/delete flows
  - one-shot desired-state migration

## Execution steps

1. **Schema + catalog migration** — new agentskills schema, move 6 skills
   into `skills/vetted/`, delete old registries.
2. **Core refactor** — ref grammar, union loader, `SUPPORTED_CLAWS_BY_DEFAULT`,
   materializer, `skills_local.py`, one-shot state migration.
3. **CLI surface** — `add/edit/remove`, updated `list/show`, attach error
   paths.
4. **GUI backend** — POST/PUT/DELETE + unioned list endpoint.
5. **GUI frontend** — drop tabs, add create form, source/support badges.
6. **Slash command** — `.claude/commands/skill-create.md`.
7. **Test rewrite** + add the two e2e tests below.

## Acceptance criteria

### AC-1: CLI end-to-end against a Hermes agent

```bash
clm skill add local/e2e-cli-demo \
    --description "E2E test skill via CLI" \
    --body-file /tmp/skill.md

clm skill list | grep -q "local/e2e-cli-demo"
clm skill show local/e2e-cli-demo                            # exits 0

clm agent skill attach local/e2e-cli-demo --agent <hermes-agent>

clm agent skill get --agent <hermes-agent> | grep -q "local/e2e-cli-demo"
clm agent exec <hermes-agent> -- ls ~/.hermes/skills/clawrium/ \
    | grep -q "e2e-cli-demo"
clm agent exec <hermes-agent> -- cat \
    ~/.hermes/skills/clawrium/e2e-cli-demo/SKILL.md \
    | grep -q "E2E test skill via CLI"
```

**Pass**: every command exits 0, skill file is present on the Hermes host
with expected frontmatter, `clm agent skill get` lists it.

### AC-2: GUI end-to-end against a Hermes agent

1. Open `/skills`, click **+ Create Skill**.
2. Fill form: `name=e2e-gui-demo`,
   `description=E2E test skill via GUI`, small markdown body. Submit.
3. New card appears in unified list with `local` badge and `hermes ✓`
   support badge.
4. Navigate to Hermes agent's page → **Skills** tab → select
   `local/e2e-gui-demo` → **Install**.
5. After apply finishes, agent's installed-skills list shows
   `local/e2e-gui-demo`.
6. Out-of-band CLI assertion:
   `clm agent exec <hermes-agent> -- test -f
   ~/.hermes/skills/clawrium/e2e-gui-demo/SKILL.md` exits 0.

### Negative AC

- `clm agent skill attach local/e2e-cli-demo --agent <openclaw-agent>`
  exits non-zero with `ClawNotSupported`.
- GUI install button on openclaw/zeroclaw agents is disabled with a
  "Not yet supported on this agent type" tooltip.

## Test strategy

- **Unit**: ref parser, union loader, conflict detection, name
  immutability, one-shot migration, materializer per claw, supported-claw
  gate.
- **Integration**: CLI `add → list → show → edit → remove` round-trip;
  CLI `add → agent skill attach → agent skill get` against a mocked
  agent; GUI POST/PUT/DELETE through FastAPI test client.
- **E2E (real Hermes agent)**: AC-1 and AC-2 above. Runs against a
  pre-provisioned Hermes agent on a host configured in `hosts.json`.
- **Lint / type**: `make lint`, `make test`, `make test-cov` all green.

## Risks

- **Breaking change**: every existing `<registry>/<name>` ref in user
  state files becomes invalid. Mitigated by one-shot `read_state`
  migration.
- **Openclaw / zeroclaw users**: any existing skill installs on those
  claws will return `ClawNotSupported` on the next attach attempt. Old
  installs already on disk are not removed — they just become un-managed
  until the claw is re-enabled. Calling this out in the PR body and
  release notes.
- **GUI form UX**: agentskills format has free-form `prerequisites` —
  keep the GUI form minimal in v1 (required fields + body), add advanced
  fields once the surface stabilises.
- **Per-claw mapping drift**: hardcoded table is the only thing standing
  between a half-wired claw and a broken install. PR review must treat
  changes to `SUPPORTED_CLAWS_BY_DEFAULT` as gated.

## Subtasks

None — execute as a single PR. Surface is large but tightly coupled
(grammar → loader → materializer → CLI → GUI), and splitting would force
intermediate states with broken refs.

---

## Planning

**Stage**: planning
**Skill**: /itx:plan-create
**Timestamp**: 2026-05-29T00:00:00Z
**Model**: claude-opus-4-7

```prompt
run /itx:plan-create 411 Now create a plan file, send PR, and wait for me to review the PR. Do not add clauses the root issue or closes four one one in the PR. Just add ref the issue.
```

**Output**: `.itx/411/00_PLAN.md` (this file).
