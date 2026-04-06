---
description: Execute the plan for an issue (parent or subtask)
---

Execute the implementation plan for GitHub issue $ARGUMENTS.

Steps:
1. Fetch the issue and find the plan in comments
2. Read the plan phases and entry/exit criteria
3. Update labels: add `in-progress`
4. Implement each phase in order:
   - Verify entry criteria before starting
   - Make the changes
   - Verify exit criteria (tests pass)
5. After all phases complete, create a PR
6. Request review: `/clm-review-pr`

For parallel execution: add `in a subtree` or `--worktree` to work in a git worktree.
