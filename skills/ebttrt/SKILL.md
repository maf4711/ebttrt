---
name: ebttrt
description: >
  Run the ebttrt Grok harness for real: begin a loop, consult the phase,
  implement, prove, done. Use when the user says ebttrt, "even better
  than the real thing", "run the loop", /ebttrt, or starts multi-file
  feature work / a real bugfix.
---

# ebttrt

Execute this, do not only describe it.

## Pipeline

```bash
ebttrt consult "$ARGUMENTS"
ebttrt begin "$ARGUMENTS" --phase <consult.start>
# do the phase (one skill). spawn ebttrt-planner / ebttrt-builder / ebttrt-reviewer as needed
ebttrt prove --record
ebttrt done
```

`$ARGUMENTS` is the user goal. If empty, run `ebttrt` (dashboard) and ask for a goal.

| Phase | Skill | Agent |
|---|---|---|
| plan | `ebttrt-plan` | `ebttrt:ebttrt-planner` |
| test | `ebttrt-tdd` | `ebttrt:ebttrt-builder` |
| implement | this file | `ebttrt:ebttrt-builder` |
| review | `ebttrt-review` | `ebttrt:ebttrt-reviewer` |
| verify | `ebttrt-verify` | `ebttrt:ebttrt-verifier` |

Never skip `ebttrt prove --record`. `ebttrt done` reuses a **fresh** prove (same HEAD + dirty_digest). After edits, prove again.

## Implement

Smallest change. AUTOHEAL local failures. Ask before force-push, `rm -rf`, prod, live money. Reuse Superpowers / Ruflo / repo skills.

## Context budget

One phase skill at a time. Dashboard: `ebttrt`. Do not load the whole catalog.
