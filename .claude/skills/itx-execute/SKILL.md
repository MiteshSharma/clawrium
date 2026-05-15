---
name: itx:execute
description: Execute the plan for an issue (parent or subtask)
argument-hint: "[orchestrate] <issue-number> [in a subtree|--worktree]"
---
name: itx:execute

# Issue Execution

Execute the implementation plan for a GitHub issue.

## Orchestrate Mode

Triggered by `orchestrate` as the **first token** in arguments
(e.g. `/itx:execute orchestrate 112`). Use when the issue is a **parent
with linked subtasks** and you want a hands-off, stacked-PR pipeline
across all subtasks.

### Preconditions

- Parent issue exists and has sub-issues linked (via GitHub
  `addSubIssue`). Detect via:
  ```bash
  gh issue view <parent> --json title,body,labels && \
  gh api graphql -f query='query($owner: String!, $repo: String!, $num: Int!) {
    repository(owner: $owner, name: $repo) {
      issue(number: $num) {
        subIssues(first: 50) { nodes { number title state } }
      }
    }
  }' -f owner="$OWNER" -f repo="$REPO" -F num=<parent>
  ```
- `tmux` available on the host. If not, fail with a clear message —
  orchestrate mode requires tmux.
- `.claude/itx-config.json` `mcp.review_enabled: true`. If review is
  not enabled, fail — orchestrate mode requires ATX to gate handoffs.
- A plan file exists at `.itx/<parent>/00_PLAN.md` (created by
  `/itx:plan-create`). Refuse to start otherwise.

### Orchestration contract

The orchestrator (the claude session that runs orchestrate mode) does
**only these things**:

1. Creates worktrees + branches + tmux windows for each subtask.
2. Spawns a child claude session per subtask via
   `claude --dangerously-skip-permissions '/itx:execute <N>'` in the
   subtask's worktree.
3. Polls subtask PR state every ~5 minutes.
4. When a subtask's PR appears (signal that ATX cleared inside the
   child), spawns the **next** subtask with the correct stacked base.
5. Escalates to the user when a child reports it is stuck after 3 ATX
   iterations without clearing Rating > 3/5.

The orchestrator does **NOT**:

- Touch source code.
- Run tests / lint directly.
- Merge PRs. Merging is the user's decision.
- Bypass ATX or use `--no-verify`.
- Spawn all subtask windows up front. Windows are created **on demand**
  when the predecessor's PR is open with clean ATX.

### Stacked PR layout

Given subtasks A, B, C, D (in dependency order from sub-issue
metadata), the orchestrator opens each child's PR against the
**predecessor's branch**, not main:

| Sub | Branch | PR base |
|---|---|---|
| A | `issue-<A>-<slug>` | `main` |
| B | `issue-<B>-<slug>` | `issue-<A>-<slug>` |
| C | `issue-<C>-<slug>` | `issue-<B>-<slug>` |
| D | `issue-<D>-<slug>` | `issue-<C>-<slug>` |

As predecessors merge, GitHub auto-updates downstream PR bases to main.

### tmux layout

- Session name: `itx/<parent>` (e.g. `itx/112`).
- One window per subtask, named `subtask-<letter>` or
  `issue-<N>` if subtasks have no obvious ordering letter.
- Created on demand. User attaches with `tmux attach -t itx/<parent>`.

### Step-by-step

1. **Parse args.** Extract `orchestrate` token + parent issue number.
   Fall through to regular execution mode if `orchestrate` absent.

2. **Verify preconditions** (above). On failure, exit with a clear
   message citing the missing precondition.

3. **Enumerate subtasks.** Order by sub-issue number (creation order).
   Treat order as dependency order unless the plan file specifies
   otherwise.

4. **Create tmux session:**
   ```bash
   tmux has-session -t "itx/${PARENT}" 2>/dev/null || \
     tmux new-session -d -s "itx/${PARENT}"
   ```

5. **Spawn subtask A:**
   ```bash
   REPO_NAME=$(basename $(git rev-parse --show-toplevel))
   REPO_PARENT=$(dirname $(git rev-parse --show-toplevel))
   WORKTREE_A="${REPO_PARENT}/${REPO_NAME}-issue-${A_NUM}"
   BRANCH_A="issue-${A_NUM}-<slug>"

   git worktree add "$WORKTREE_A" -b "$BRANCH_A" main

   tmux new-window -t "itx/${PARENT}" -n "subtask-A" -c "$WORKTREE_A"
   tmux send-keys -t "itx/${PARENT}:subtask-A" \
     "claude --dangerously-skip-permissions '/itx:execute ${A_NUM}'" Enter
   ```

6. **Poll predecessor PR state every 5 minutes:**
   ```bash
   gh pr list --repo "$OWNER/$REPO" --head "$BRANCH_A" \
     --json number,state,reviewDecision,body --jq '.[0]'
   ```
   The child claude opens its PR **only after** its internal ATX loop
   reaches Rating > 3/5 with no blockers. PR existence ⇒ ATX cleared.

   **Do not poll faster than 5 minutes.** ATX iterations take minutes;
   faster polling burns cache without changing outcomes.

7. **On predecessor PR open, spawn next subtask:**
   - Create worktree at `${REPO_PARENT}/${REPO_NAME}-issue-${NEXT_NUM}`.
   - Branch from the predecessor's branch (not main).
   - Create tmux window, run child claude.
   - Override the child's default PR base by passing the predecessor's
     branch name in the prompt:
     ```bash
     claude --dangerously-skip-permissions \
       "/itx:execute ${NEXT_NUM} --pr-base=${PREV_BRANCH}"
     ```
     (Child sessions in standard mode must honor `--pr-base` — see
     "PR base override" below.)

8. **Repeat** until all subtasks have open PRs.

9. **Final state.** Orchestrator reports a summary table with each
   subtask's PR URL, ATX rating, and base branch. Then stands down.
   Merging is the user's decision; merging happens bottom-up.

### Escalation: stuck child

A child session that fails to clear Rating > 3/5 after 3 ATX iterations
writes a marker comment on its own PR (or its issue if no PR exists
yet) with body starting `[ITX-STUCK]` and pauses.

The orchestrator's polling loop also matches `[ITX-STUCK]` comments on
the predecessor's issue. On detection:

1. Halt the spawn pipeline (do not start the next subtask).
2. Surface the blockage to the user with: the subtask number, the ATX
   feedback summary, and a recommended action.
3. Wait for user direction (extend iterations, downgrade scope,
   abandon, or manual takeover).

### PR base override (child contract)

When a child receives `--pr-base=<branch>`, it MUST:

- Open its PR against that branch, not `main`.
- Include `Stacked on top of <branch>` in the PR body so reviewers know
  the dependency chain.

If the child's mode does not support `--pr-base`, the orchestrator
falls back to opening the PR itself after the child finishes:

```bash
gh pr edit <pr-num> --base "$PREV_BRANCH"
```

### Failure modes

- **No subtasks found**: fail with "Issue #N has no linked sub-issues.
  Use `/itx:execute <N>` (without orchestrate) for direct execution."
- **Subtask already has merged PR**: skip and advance to next.
- **Subtask already has open PR**: skip the spawn step; treat as
  "ATX-cleared, advance to next".
- **Worktree already exists**: re-use if branch matches expected name;
  fail otherwise (manual cleanup required).
- **tmux session orphaned**: re-use if exists; do not create duplicate.

### When to use orchestrate mode

- Parent issue with 2+ linked subtasks where order matters.
- You want hands-off execution across the whole chain.
- ATX is enabled and tmux is available.

### When NOT to use orchestrate mode

- Single-issue (no subtasks) — use regular mode.
- ATX disabled in `.claude/itx-config.json` — gating signal missing.
- You want manual control between every subtask — use regular mode
  with explicit handoffs.

## Worktree Mode (Recommended for Parallel Execution)

Triggered by `in a subtree` or `--worktree` in arguments. Enables working on multiple issues simultaneously.

### Worktree Naming Convention
```
<repo-parent>/<repo-name>-issue-<number>/
```

Example:
```
~/projects/myrepo/           # Main repo
~/projects/myrepo-issue-35/  # Worktree for issue 35
~/projects/myrepo-issue-42/  # Worktree for issue 42
```

### Worktree Execution Steps

1. **Create Worktree**:
   ```bash
   REPO_NAME=$(basename $(git rev-parse --show-toplevel))
   REPO_PARENT=$(dirname $(git rev-parse --show-toplevel))
   WORKTREE_PATH="${REPO_PARENT}/${REPO_NAME}-issue-${NUMBER}"

   git worktree add "${WORKTREE_PATH}" -b issue-${NUMBER}-<slug> main
   ```

2. **Launch Execution**:

   **If tmux available** (interactive execution in background):
   ```bash
   # Create session if not exists
   tmux has-session -t "itx/exec" 2>/dev/null || tmux new-session -d -s "itx/exec"

   # Create window and run claude interactively (no -p flag so you can watch execution)
   tmux new-window -t "itx/exec" -n "issue-${NUMBER}" -c "${WORKTREE_PATH}"
   tmux send-keys -t "itx/exec:issue-${NUMBER}" \
     "claude --dangerously-skip-permissions '/itx:execute ${NUMBER}'" Enter

   echo "Spawned in tmux 'itx/exec:issue-${NUMBER}'"
   echo "Attach: tmux attach -t itx/exec"
   ```

   **If tmux not available** (fallback):
   Use `AskUserQuestion` to ask:
   - **Subagent**: Spawn Task agent in worktree (non-interactive)
   - **Same session**: Continue in current session (interactive, will ask permissions)

3. **Exit**: After spawning tmux window, exit current execution (work continues in tmux)

### Worktree Cleanup

After PR is merged:
```bash
# Remove worktree
git worktree remove ../<repo>-issue-35

# Or force remove if dirty
git worktree remove --force ../<repo>-issue-35

# Clean up tmux window
tmux kill-window -t "itx/exec:issue-35"
```

## GitHub Project Board (Optional)

Project board integration is **optional** and controlled via `.claude/itx-config.json`.

### Check if Project Board is Enabled

```bash
ITX_CONFIG="$(git rev-parse --show-toplevel)/.claude/itx-config.json"
if [ -f "$ITX_CONFIG" ]; then
  PROJECT_ENABLED=$(jq -r '.github.project_board.enabled // false' "$ITX_CONFIG")
  if [ "$PROJECT_ENABLED" = "true" ]; then
    # Load project board configuration
    PROJECT_ID=$(jq -r '.github.project_board.project_id' "$ITX_CONFIG")
    STATUS_FIELD_ID=$(jq -r '.github.project_board.status_field_id' "$ITX_CONFIG")
    BACKLOG_ID=$(jq -r '.github.project_board.status_options.backlog' "$ITX_CONFIG")
    READY_ID=$(jq -r '.github.project_board.status_options.ready' "$ITX_CONFIG")
    EXECUTING_ID=$(jq -r '.github.project_board.status_options.executing' "$ITX_CONFIG")
    IN_REVIEW_ID=$(jq -r '.github.project_board.status_options.in_review' "$ITX_CONFIG")
    DONE_ID=$(jq -r '.github.project_board.status_options.done' "$ITX_CONFIG")
  fi
else
  PROJECT_ENABLED="false"
fi
```

### Add Issue to Project & Set Status (if enabled)

**Only execute if `PROJECT_ENABLED="true"`**:

```bash
# Extract repository info
REMOTE_URL=$(git config --get remote.origin.url)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's/.*[:/]([^/]+\/[^/]+)(\.git)?$/\1/')
OWNER=$(echo "$OWNER_REPO" | cut -d'/' -f1)
REPO=$(echo "$OWNER_REPO" | cut -d'/' -f2)

# Get issue node ID
NODE_ID=$(gh api repos/$OWNER/$REPO/issues/<number> --jq '.node_id')

# Add to project (returns item ID)
ITEM_ID=$(gh api graphql -f query='
  mutation($projectId: ID!, $contentId: ID!) {
    addProjectV2ItemById(input: {
      projectId: $projectId
      contentId: $contentId
    }) { item { id } }
  }
' -f projectId="$PROJECT_ID" -f contentId="$NODE_ID" --jq '.data.addProjectV2ItemById.item.id')

# Set status to Executing
gh project item-edit --project-id "$PROJECT_ID" --id "$ITEM_ID" \
  --field-id "$STATUS_FIELD_ID" --single-select-option-id "$EXECUTING_ID"
```

**If project board not enabled**, skip all project board operations silently.

## Branch Protection

**NEVER push directly to the `main` branch.**

Always:
1. Work on a feature branch: `issue-<number>-<slug>`
2. Push to the feature branch
3. Create a PR targeting `main`

## Instructions

1. **Fetch Issue**: Get full issue details
   ```bash
   gh issue view <number> --json number,title,body,labels,comments
   ```

2. **Identify Issue Type**:
   - **Subtask**: Title starts with `[Parent #N]`
   - **Parent with subtasks**: Has subtask issues linked
   - **Parent without subtasks**: Direct execution

3. **Route Execution**:

### If Parent with Subtasks

1. List subtasks by searching for issues with `[Parent #<number>]` in title
2. For each subtask (in order):
   - Spawn a subagent to execute the subtask
   - Wait for subtask completion
   - Verify subtask is marked done
3. Once all subtasks complete, close parent issue

### If Parent without Subtasks OR Subtask

1. **Log Start**: Add execution start comment
   ```markdown
   ## Execution Started

   Beginning implementation...

   ---

   <details>
   <summary>Prompt Log</summary>

   **Stage**: execution
   **Skill**: /itx:execute
   **Timestamp**: <ISO timestamp>
   **Model**: <model>

   ```prompt
   <user prompt that triggered execution>
   ```

   </details>
   ```

2. **Update Status to Executing** (if project board enabled):
   Use the conditional project board commands above.
   If not enabled, skip this step silently.

3. **Read Plan**: Find the implementation plan in issue comments or `.itx/<N>/01_EXECUTION.md`

4. **Load Build Configuration**:
   ```bash
   ITX_CONFIG="$(git rev-parse --show-toplevel)/.claude/itx-config.json"
   if [ -f "$ITX_CONFIG" ]; then
     TEST_CMD=$(jq -r '.build.test_command // "make test"' "$ITX_CONFIG")
     LINT_CMD=$(jq -r '.build.lint_command // "make lint"' "$ITX_CONFIG")
   else
     TEST_CMD="make test"
     LINT_CMD="make lint"
   fi
   ```

5. **Create Execution Checklist**:

   **CRITICAL**: ALWAYS create task checklist before any execution. Do not skip this step.

   Parse the implementation plan and create tasks for tracking:

   a. **Create Implementation Tasks**:
      For each phase/step in the plan, create a task:
      ```
      TaskCreate(
          subject="Implement: <phase/step description>",
          description="<detailed requirements from plan>",
          activeForm="Implementing <phase/step>"
      )
      ```

   b. **Create Verification Tasks**:
      ```
      TaskCreate(
          subject="Run test suite",
          description="Execute configured test command and ensure all tests pass",
          activeForm="Running tests"
      )

      TaskCreate(
          subject="Run linter",
          description="Execute configured lint command and fix any issues",
          activeForm="Running linter"
      )
      ```

   c. **Set Dependencies** (if needed):
      ```
      TaskUpdate(
          taskId="<later-task-id>",
          addBlockedBy=["<prerequisite-task-id>"]
      )
      ```

   d. **Review Task List**:
      ```
      TaskList()  # Confirm all tasks created correctly
      ```

6. **Execute Tasks Systematically**:

   a. Get Next Task: `TaskList()` - Find first pending task with no blockedBy

   b. Start Task: `TaskUpdate(taskId="<task-id>", status="in_progress")`

   c. Execute Changes: Implement the task requirements
      - Make code changes
      - Write/update tests
      - Follow existing code patterns

   d. Complete Task: `TaskUpdate(taskId="<task-id>", status="completed")`

   e. Check Progress: `TaskList()` - See remaining tasks

   f. Repeat until all implementation tasks are completed

7. **Execute Verification Tasks**:

   Follow the same pattern as implementation:
   - Mark verification task as in_progress
   - Run verification using configured commands ($TEST_CMD, $LINT_CMD)
   - Mark as completed
   - Move to next verification task

8. **Create PR**:

   **If in worktree mode**: Branch already exists (created during worktree setup)
   ```bash
   git add <files>
   git commit -m "<message>"
   git push -u origin issue-<number>-<slug>
   gh pr create --title "<title>" --body "Closes #<number>"
   ```

   **If in regular mode**: Create branch first
   ```bash
   git checkout -b issue-<number>-<slug>
   git add <files>
   git commit -m "<message>"
   git push -u origin issue-<number>-<slug>
   gh pr create --title "<title>" --body "Closes #<number>"
   ```

   **WARNING**: Never push to `main`. Always push to feature branch and create PR.

## Progress Tracking with Tasks

### Creating Tasks from Plan

When reading the implementation plan, extract:
- **Implementation steps**: Each becomes a task
- **Files to modify**: Include in task descriptions
- **Dependencies**: Set using addBlockedBy
- **Acceptance criteria**: Include in task descriptions

### Task Naming Convention

```
subject: "Implement: <what>"
description: "<detailed requirements>"
activeForm: "Implementing <what>"
```

Examples:
```
subject: "Implement: Update CLI help text for new terminology"
description: "Update all help text in src/cli/main.py to use new terminology"
activeForm: "Updating CLI help text"

subject: "Implement: Refactor service.py function names"
description: "Rename functions: old_name -> new_name, another_old -> another_new"
activeForm: "Refactoring service.py"
```

### Standard Verification Checklist

Always create these verification tasks:
1. Run test suite (using configured test command)
2. Run linter (using configured lint command)
3. Verify no regressions

### When You Get Lost

If execution feels unclear or you lose track of progress:
1. Run `TaskList()` to see current state
2. Check which task is in_progress
3. Review that task's description
4. Complete current task before starting next
5. Never jump ahead without marking tasks complete

## Subagent Spawning (for Parent with Subtasks)

Use the Task tool to spawn subagents:
```
Task(
  subagent_type="general-purpose",
  prompt="Execute /itx:execute <subtask-number>",
  description="Execute subtask #<number>"
)
```

Execute subtasks sequentially to avoid conflicts.

## Completion Check (for Subtasks)

After completing a subtask, check if all sibling subtasks are done:
```bash
# Find parent number from title [Parent #N]
# List all subtasks for that parent
# If all closed, close the parent
```

## Configuration

Build commands are configurable via `.claude/itx-config.json`:

```json
{
  "build": {
    "test_command": "npm test",
    "lint_command": "npm run lint"
  }
}
```

**Defaults** (no config): `make test`, `make lint`

See [CONFIG.md](../../CONFIG.md) for full configuration options.

## Notes

- **ALWAYS create task checklist before execution** - Do not skip this step
- **Use TaskList() frequently** to maintain awareness of progress
- **Complete tasks sequentially** unless explicitly marked as parallel
- **If you feel lost**, check TaskList() to reorient
- Project board updates are optional and only execute if configured
- Build commands automatically adapt to project configuration
- Subtasks can use cheaper/faster models (Haiku)
- Parent orchestration can use any model
- Always verify before marking complete
- Don't skip the verification step

## Prompt Logging

**REQUIRED**: Append prompt log to `.itx/<N>/01_EXECUTION.md`.

See [AGENTS.md](../../../AGENTS.md#prompt-logging-standard) for format specification.
