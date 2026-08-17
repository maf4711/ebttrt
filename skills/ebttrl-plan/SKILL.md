---
name: ebttrl-plan
description: >
  Write a short implementation blueprint before code. Use when the user
  runs /ebttrl-plan, asks for a plan, or ebttrl reaches the plan phase.
---

# ebttrl-plan

Produce a blueprint. Do not edit product code in this phase.

1. Read the request and the current tree. Stay inside the workspace.
2. If the approach is still ambiguous, ask **one** question, then stop.
3. Name the files you will change, the tests that prove it, and the verify command.
4. Prefer an existing pattern in-repo over a new abstraction.

## Output

```markdown
## Goal
## Approach
## Files
- path — why
## Tests
- command / case
## Verify
- exact command
## Out of scope
```

If you spawn a child, use agent `ebttrl-planner` (read-only).
