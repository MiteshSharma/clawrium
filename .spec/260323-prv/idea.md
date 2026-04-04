# Idea: Slash Command for Local PR Review with ATX

> **Status**: idea
> **Created**: 2026-03-23
> **Author**: devashish

## Raw Thoughts

Add a slash command to review PR locally using atx. This command should create a worktree, pull a PR in that worktree and use atx to review the PR.

## Socratic Exploration

### Customer Value

1. **Who specifically experiences this problem?**
   - _Answer:_ Developers who want to run ATX code reviews on PRs before merging

2. **What is the measurable impact on them today?**
   - _Answer:_ Manual steps: checkout PR, run atx review, cleanup - takes time and pollutes working directory

3. **How would they describe success if this were solved?**
   - _Answer:_ Single command: `/clawrium:review-pr 123` triggers full ATX review on PR #123 in isolated worktree

### Pain Point Analysis

4. **What is the core pain point this addresses?**
   - _Answer:_ Getting ATX reviews on PRs requires manual worktree management and cleanup

5. **How frequently do users encounter this pain?**
   - _Answer:_ Every PR review - multiple times per day

6. **What workarounds exist today, and why are they insufficient?**
   - _Answer:_ Manual: `git worktree add`, `gh pr checkout`, `atx review`, cleanup. Error-prone and tedious.

### Existing Solutions

7. **What solutions already exist (internal or external)?**
   - _Answer:_ Manual worktree + atx review, or review in main working directory (pollutes state)

8. **Why are current solutions not enough?**
   - _Answer:_ Too many manual steps, easy to forget cleanup, disrupts current work

9. **Could an existing solution be enhanced instead of building new?**
   - _Answer:_ No - this is a new workflow automation

10. **If yes, why is enhancement not preferred? If no, why not?**
    - _Answer:_ N/A - new capability needed

### Timing & Priority

11. **Why solve this now versus later?**
    - _Answer:_ ATX reviews are becoming standard workflow; friction slows adoption

12. **What happens if we don't solve this?**
    - _Answer:_ Developers skip ATX reviews on PRs or do them inconsistently

## Initial Scope

- [ ] Create slash command `/clawrium:review-pr <pr-number>`
- [ ] Create git worktree in temp location
- [ ] Pull PR into worktree using `gh pr checkout`
- [ ] Run `atx review` with appropriate flags
- [ ] Output review results
- [ ] Cleanup worktree after review

## Open Questions

- Should the worktree be auto-cleaned or kept for inspection?
- What format should the review output be in (json/text)?
- Should this support reviewing PRs from forks?
- Where should the worktree be created? (temp dir, `.worktrees/`, etc.)

---

<details>
<summary>Prompt Log</summary>

```yaml
- model: anthropic.claude-opus-4-5-20251101-v1:0
  date: 2026-03-23
  type: idea-capture
  prompt: |
    add a slash command to review pr locally using atx. this command should 
    create a worktree, pull a pr in that worktree and use atx to review the pr.
```

</details>
