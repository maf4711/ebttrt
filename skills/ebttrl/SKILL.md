---
name: ebttrl
description: >
  Run the ebttrl Grok harness for real: begin a loop, consult the phase,
  implement, prove, done. Use when the user says ebttrl, "even better
  than the real thing", "run the loop", /ebttrl, or starts multi-file
  feature work / a real bugfix.
---

# ebttrl

Execute this, do not only describe it.

## Pipeline

```bash
ebttrl consult "$ARGUMENTS"
ebttrl begin "$ARGUMENTS" --phase <consult.start>
# do the phase (one skill). spawn ebttrl-planner / ebttrl-builder / ebttrl-reviewer as needed
ebttrl prove --record
ebttrl done
```

`$ARGUMENTS` is the user goal. If empty, run `ebttrl` (dashboard) and ask for a goal.

| Phase | Skill | Agent |
|---|---|---|
| plan | `ebttrl-plan` | `ebttrl:ebttrl-planner` |
| test | `ebttrl-tdd` | `ebttrl:ebttrl-builder` |
| implement | this file | `ebttrl:ebttrl-builder` |
| review | `ebttrl-review` | `ebttrl:ebttrl-reviewer` |
| verify | `ebttrl-verify` | `ebttrl:ebttrl-verifier` |

Never skip `ebttrl prove --record`. `ebttrl done` reuses a **fresh** prove (same HEAD + dirty_digest). After edits, prove again.

## Implement

Smallest change. AUTOHEAL local failures. Ask before force-push, `rm -rf`, prod, live money. Reuse Superpowers / Ruflo / repo skills.

## Context budget

One phase skill at a time. Dashboard: `ebttrl`. Do not load the whole catalog.
