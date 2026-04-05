# Contributing to Clawrium

## Development Workflow

GitHub Issues are the single source of truth. This document describes the issue lifecycle and how to contribute.

## Issue Lifecycle

```
┌──���──────────────────────────────────────────────────────────────────────────┐
│                              ISSUE LIFECYCLE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

    New Issue                                    New Bug
        │                                           │
        ▼                                           ▼
  ┌───────────┐                             ┌─────────────────┐
  │   INBOX   │                             │  NEEDS TRIAGE   │
  │ (no label)│                             │ (needs-triage)  │
  └─────┬─────┘                             └────────┬────────┘
        │                                            │
        │ /clm:triage                                │
        │ Assign workflow label                      │
        ▼                                            │
  ┌─────────────────┐                               │
  │    PLANNING     │◄──────────────────────────────┘
  │   (planning)    │
  └────────┬────────┘
           │
           │ /clm:plan
           │ - Create implementation plan
           │ - Optionally create subtask issues
           ▼
  ┌─────────────────┐
  │      READY      │
  │     (ready)     │
  └────────┬────────┘
           │
           │ /clm:execute
           ▼
  ┌─────────────────┐
  │   IN PROGRESS   │
  │  (in-progress)  │
  └────────┬────────┘
           │
           │ /clm:verify
           │ Open PR
           ▼
  ┌─────────────────┐
  │    IN REVIEW    │
  │   (in-review)   │
  └────────┬────────┘
           │
           │ PR merged
           ▼
  ┌─────────────────┐
  │      DONE       │
  │    (closed)     │
  └─────────────────┘
```

## Issue States

| State | Label | Description | Entry | Exit |
|-------|-------|-------------|-------|------|
| **INBOX** | (none) | New issues without workflow labels | Issue created | `/clm:triage` |
| **NEEDS TRIAGE** | `needs-triage` | Needs more information or clarification | Bug created, or needs info | Clarified → `planning` |
| **PLANNING** | `planning` | Being planned | Ready for planning | `/clm:plan` |
| **READY** | `ready` | Plan complete, ready to execute | Plan approved | `/clm:execute` |
| **IN PROGRESS** | `in-progress` | Currently being worked on | Execution started | PR opened |
| **IN REVIEW** | `in-review` | PR open for review | PR created | PR merged |
| **DONE** | (closed) | Complete | PR merged | - |

## Workflow Labels

These labels control the workflow state:

| Label | Color | Description |
|-------|-------|-------------|
| `needs-triage` | Red | Needs more information or clarification |
| `planning` | Green | Being planned |
| `ready` | Blue | Plan complete, ready for execution |
| `in-progress` | Yellow | Currently being worked on |
| `in-review` | Purple | PR open for review |

## Type Labels

These labels categorize the issue type:

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature or request |
| `documentation` | Improvements to documentation |

## Skills Reference

Use these Claude Code skills to manage the workflow:

| Skill | Purpose |
|-------|---------|
| `/clm:bug-new` | Create bug issue (asks for customer outcome) |
| `/clm:bug-update <n> <text>` | Add comment to bug |
| `/clm:issue-new` | Create feature issue (asks for customer outcome) |
| `/clm:issue-update <n> <text>` | Add comment to issue |
| `/clm:triage` | Review issues without workflow labels |
| `/clm:plan <n>` | Create implementation plan for issue |
| `/clm:execute <n>` | Execute issue (parent or subtask) |
| `/clm:verify` | Run tests and lint |
| `/clm:review-pr [n]` | Request ATX code review |
| `/clm:pr-status` | Check status of open PRs |
| `/clm:note [text]` | Quick note to NOTES.md |

## Parent/Subtask Pattern

Complex issues can be broken into subtasks:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PARENT/SUBTASK PATTERN                               │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │  PARENT ISSUE   │
                    │     #100        │
                    │    (ready)      │
                    └────────┬────────┘
                             │
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
        ┌───────────┐ ┌───────────┐ ┌───────────┐
        │ [#100]    │ │ [#100]    │ │ [#100]    │
        │ Subtask 1 │ │ Subtask 2 │ │ Subtask 3 │
        │  (done)   │ │  (done)   │ │(in-progress)│
        └───────────┘ └───────────┘ └───────────┘

    - Subtask title format: [Parent #N] <description>
    - /clm:execute on parent executes subtasks sequentially
    - Parent closes when ALL subtasks are done
```

### Rules

1. `/clm:plan` decides if subtasks are needed based on complexity
2. Subtask issues are created with `ready` label
3. Each subtask can be executed independently with `/clm:execute <subtask>`
4. Running `/clm:execute <parent>` executes all subtasks in sequence
5. Parent issue closes automatically when all subtasks complete

## Development Setup

```bash
# Clone the repository
git clone https://github.com/ric03uec/clawrium.git
cd clawrium

# Install dependencies
make install

# Run tests
make test

# Run linter
make lint

# Format code
make format
```

## Making Changes

1. **Find or create an issue** - All work should be tracked in GitHub Issues
2. **Plan the work** - Use `/clm:plan <issue>` to create an implementation plan
3. **Execute** - Use `/clm:execute <issue>` or work manually
4. **Verify** - Run `make test && make lint` or `/clm:verify`
5. **Create PR** - Reference the issue with "Closes #N"
6. **Review** - Use `/clm:review-pr` for ATX review

## Code Review

All PRs are reviewed using ATX agents. Reviews must meet:
- Rating > 3/5
- No blocking issues

See [AGENTS.md](AGENTS.md) for review format requirements.

## Issue Title Convention

Issue titles should describe the **customer outcome**:

**Good titles** (outcome-focused):
- "User can install claws without version mismatch errors"
- "User can see token usage across all agents"
- "User can backup claw configurations automatically"

**Avoid** (implementation-focused):
- "Fix version check in registry.py"
- "Add token tracking feature"
- "Implement backup command"

The `/clm:bug-new` and `/clm:issue-new` skills will prompt you for the customer outcome.
