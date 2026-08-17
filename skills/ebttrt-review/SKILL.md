---
name: ebttrt-review
description: >
  Fresh-context review of the actual diff. Use when the user runs
  /ebttrt-review, asks for a review, or ebttrt reaches the review phase.
---

# ebttrt-review

Review the **diff**, not the story of how it was written.

1. Collect the actual change: `git diff` and `git status`. If a child did the work, review that worktree / commit.
2. Prefer spawning `ebttrt-reviewer` so the parent context does not bias the review.
3. Check correctness, security (secrets, path traversal, injection), missing tests, and scope creep.
4. Write the verdict: `ebttrt review --verdict approve` or `ebttrt review --verdict revise --finding high:file:fact`.
5. Do not rewrite the feature in the review. One-file fixes may skip review. Multi-file or public API may not.

`done` refuses revise+high and refuses a drifted digest.

## Output

```markdown
## Verdict
approve | revise
## Findings
- severity: critical|high|medium|info — file:line — fact
## Missing evidence
```

Critical or high findings block remember. Fix and re-review.
