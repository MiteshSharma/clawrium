# GUI UX Overhaul — Implementation Plan

> **Status**: Draft
> **Date**: 2026-05-27
> **Version**: 26.5.4

---

## Problem Statement

The Clawrium GUI is a faithful 1:1 projection of CLI commands onto web pages. It correctly identifies core objects (Providers, Skills, Integrations) as top-level navigation, but presents them as isolated CRUD pages rather than as the connective tissue between shared configuration and agents.

The core value proposition — **configure shared artifacts once, apply to any number of agents** — is invisible in the current UI. Users cannot see "which agents use this provider?" and cannot bulk-apply artifacts to agents.

## ICP

Slightly-to-highly technical users who prefer a GUI over CLI for managing their AI agent fleets. They will still use each agent's native UI for direct interaction — Clawrium is the infrastructure and fleet management layer.

## Value Hierarchy

| Priority | Clawrium's Role | User Need |
|----------|----------------|-----------|
| **Primary** | Manage shared artifacts (Providers, Skills, Integrations, Channels) — configure once, apply to N agents | "I set up Bedrock once and all my agents can use it" |
| **Secondary** | Fleet visibility (Dashboard, Topology) — health, costs, status | "Are all my agents healthy? What am I spending?" |
| **Tertiary** | Agent interaction (exec commands, chat) — convenience | "Quick command without opening the agent's UI" |

## Customer Outcome

After this overhaul, a user can:
1. Create a provider/skill/integration and immediately see which agents use it
2. Apply any shared artifact to multiple agents in one action
3. Run commands on any agent without leaving the GUI
4. Understand their fleet's configuration graph at a glance
5. Never hit a "use the CLI" dead end

---

## Plan

### Phase 1: Core Value Prop (P0)

#### 1.1 — "Configure Once, Apply Many" Workflows on Artifact Pages

**Goal**: Make the core value prop visible and actionable on every artifact page.

**Changes per artifact page (Providers, Skills, Integrations, Channels):**

1. Add **"Used by" line** on each artifact card showing which agents reference it
2. Add **"Apply to Agents..." button** → opens multi-select agent picker → attaches artifact to all selected
3. Add **"Remove from Agent"** action when viewing expanded usage list
4. Show agent count badge on each card

**Providers page before/after:**

Before:
```
┌──────────────────┐
│ esper-bedrock     │
│ bedrock · glm-5   │
│ Key: ✓ Set        │
│ [Edit] [Remove]   │
└──────────────────┘
```

After:
```
┌──────────────────────────────────────────────┐
│ esper-bedrock                                 │
│ AWS Bedrock · zai.glm-5 · Key: ✓ Active      │
│                                               │
│ Used by: vand, doppio, staging    (3 agents) │
│                                               │
│ [Edit] [Apply to Agents...] [Remove]         │
└──────────────────────────────────────────────┘
```

**API requirements:**
- `GET /api/providers` → add `agents_using: string[]` to response
- `POST /api/providers/{id}/apply` → `{ agent_keys: string[] }` body
- Same pattern for `/api/skills` and `/api/integrations`

**Frontend work:**
- Update `ProviderCard` component to show usage
- Add `ApplyToAgentsModal` shared component (reusable across artifact types)
- Update `SkillCard` and `IntegrationCard` similarly

---

#### 1.2 — Eliminate CLI Dead Ends

**Goal**: Remove every "use the CLI" instruction from the GUI.

| Location | Current | Fix | Backend |
|----------|---------|-----|---------|
| Skills page subtitle | "Run `clawctl agent skill attach...`" | [Attach to Agent] button per card → agent picker → `POST /api/agents/{key}/skills` | API exists |
| Settings / GUI Preferences | "configure via CLI flags" | Inline editable fields → save triggers GUI restart | New: `PUT /api/settings/gui` |
| Settings / Danger Zone | Disabled button + "use CLI" | Enabled button → type-to-confirm modal → `DELETE /api/settings/reset` | New route |
| Agent Config tab | Read-only display | [Edit] button → modal → calls configure under the hood | New: `PUT /api/agents/{key}/config` |

---

### Phase 2: Complete the GUI Surface (P1)

#### 2.1 — Agent Exec / Command Runner

**Goal**: Expose `clawctl agent exec <name> -- <cmd>` in the GUI.

**New tab on Agent Detail page: "Terminal"**

```
┌──────────────────────────────────────────────────────┐
│  Run a command on this agent's host                  │
│                                                      │
│  ┌────────────────────────────────────────────┐      │
│  │ $ ▌                                        │      │
│  └────────────────────────────────────────────┘      │
│  [Run]  Prefix: clawctl agent exec vand --           │
│                                                      │
│  ─── Recent Commands ───                             │
│  $ --version                 hermes v2026.5.7        │
│  $ health                    status: ok, 42ms        │
│                                                      │
│  ─── Quick Actions ───                               │
│  [Version] [Health Check] [Show Config] [Restart]    │
└──────────────────────────────────────────────────────┘
```

**Backend:**
- New route: `POST /api/agents/{key}/exec` → body: `{ command: string }` → returns stdout/stderr
- Subprocess: calls `clawctl agent exec {key} -- {command}`
- Timeout: 30s default, configurable

**Frontend:**
- New `TerminalTab` component in `components/agent-detail/`
- Command input + output display (monospace, scrollable)
- Command history (localStorage persisted)
- Quick-action buttons for common commands (configurable per agent type)

---

#### 2.2 — Agent Overview Panel (All Attached Artifacts)

**Goal**: Show the full relationship graph for a single agent in one view.

**Replace or enhance the Configuration tab:**

```
┌────────────────────────────────────────────────────┐
│  PROVIDER                                          │
│  esper-bedrock · Bedrock · zai.glm-5               │
│  [Change Provider] [View in Providers]             │
│                                                    │
│  SKILLS (2 installed)                              │
│  clawrium/tdd v0.1.0              [Detach]         │
│  hermes/web-search v1.2.0         [Detach]         │
│                          [+ Attach Skill]          │
│                                                    │
│  INTEGRATIONS (1 connected)                        │
│  work-atlassian · 3/5 keys set    [Fix] [Detach]  │
│                          [+ Connect Integration]   │
│                                                    │
│  GATEWAY                                           │
│  Port: 40012 · URL: http://clawdmin:40012          │
└────────────────────────────────────────────────────┘
```

**Key properties:**
- Every attached artifact has detach/remove action
- Missing/broken items surface with [Fix] action
- Links back to artifact page ("View in Providers")
- This is the **inverse view** of Phase 1 — artifact pages show "which agents use this", agent overview shows "which artifacts are attached here"

**API:** Existing endpoints suffice — compose from `/api/fleet/agents/{key}`, `/api/agents/{key}/skills`, and integration data.

---

#### 2.3 — Restructure Navigation with Section Headers

**Goal**: The sidebar teaches the product's mental model.

**Proposed navigation:**

```
FLEET OVERVIEW
  Dashboard         (health + costs)
  Topology          (network map)

SHARED CONFIGURATION
  Providers         (LLM keys & models)
  Skills            (capabilities)
  Integrations      (external services)
  Channels          (communication)

AGENTS
  Fleet Agents      (all agents list)
  + Add Agent

SYSTEM
  Settings
  Usage & Costs
```

**Key changes:**
- Section headers added: "Fleet Overview", "Shared Configuration", "Agents", "System"
- "Shared Configuration" label communicates WHY these are fleet-level
- "Fleet Agents" becomes its own nav item (currently only a table on Dashboard)
- "+ Add Agent" as persistent nav action
- "Channels" added as new entity type
- Settings + Usage grouped as low-frequency "System" tasks

**Frontend work:**
- Update `Sidebar` component to support section headers
- Add `/agents` route (fleet agent list with lifecycle actions)
- Add `/channels` route (new page, TBD scope)
- Move Usage from floating toast to dedicated page

---

### Phase 3: Activation & Differentiation (P2)

#### 3.1 — Onboarding Wizard (First-Run)

**Goal**: Teach the "shared config" mental model from minute one.

**Flow:**
1. Welcome — "Configure shared infrastructure once, apply to any agent"
2. Add Host — IP, SSH user, test connection
3. Create Provider — "This provider will be available to ALL your agents"
4. Deploy First Agent — choose type, assign the provider just created
5. Done — links to: agent UI, add skills, view dashboard

**Trigger**: Show when `agents.length === 0` on first GUI load.

**Key design decision**: Provider created BEFORE agent to establish the mental model that providers are fleet-level resources, not per-agent configs.

---

#### 3.2 — Full Artifact Topology

**Goal**: Topology shows ALL relationship types, not just Host→Agent→Provider.

**Additional edges:**
- Agent → Skill (attached skills)
- Agent → Integration (connected integrations)
- Agent → Channel (future)

**Additional node types:**
- Skill nodes (grouped by registry)
- Integration nodes (show connection health)

**Filtering:**
- Layer toggles: [Providers] [Skills] [Integrations] [Channels]
- Default: Providers only (for visual clarity)

**Why**: When a user sees one skill node connected to 4 agent nodes, the "configure once, apply many" value becomes visually obvious.

---

## Dependencies & Sequencing

```
Phase 1.1 (Apply-to-Agents) ──→ Phase 2.2 (Agent Overview)
         ↓                              ↑
Phase 1.2 (CLI dead ends) ──→ Phase 2.1 (Exec runner)
                                        ↓
Phase 2.3 (Nav restructure) ──→ Phase 3.1 (Onboarding)
                                        ↓
                                Phase 3.2 (Topology)
```

- Phase 1.1 and 1.2 are independent of each other — can parallelize
- Phase 2.2 depends on 1.1 (needs the "used by" API data)
- Phase 2.3 (nav restructure) should happen after feature pages exist
- Phase 3 depends on all prior phases being stable

## Effort Estimates

| Phase | Items | Effort | Notes |
|-------|-------|--------|-------|
| 1.1 | Apply-to-agents workflows | ~3-4 days | New API fields + shared modal component |
| 1.2 | CLI dead ends | ~2 days | Mostly frontend, one new API route |
| 2.1 | Exec runner | ~3 days | New backend route + frontend tab |
| 2.2 | Agent overview | ~2 days | Composing existing data into new view |
| 2.3 | Nav restructure | ~2 days | Frontend restructure + new Fleet Agents page |
| 3.1 | Onboarding | ~3 days | Multi-step wizard, conditional rendering |
| 3.2 | Full topology | ~4 days | New node types, edge calculations, filtering |
| **Total** | | **~19-20 days** | |

## Success Criteria

- [ ] Every artifact card shows "Used by: N agents" with an apply button
- [ ] Zero instances of "use the CLI" text in the GUI
- [ ] Agent exec commands work from Agent Detail → Terminal tab
- [ ] Agent overview shows provider + skills + integrations in one panel
- [ ] Navigation has section headers communicating the mental model
- [ ] First-run wizard activates when no agents exist
- [ ] Topology shows skill and integration edges (toggleable)

## Out of Scope

- Agent-native UI embedding (users go to the agent's own UI for that)
- Chat UX improvements (tertiary feature, not investing here)
- Mobile responsiveness (desktop-first product)
- Multi-user / auth (single-user fleet management tool)
