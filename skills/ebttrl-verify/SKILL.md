---
name: ebttrl-verify
description: >
  Evidence before any done/fixed/passing claim. Use when the user runs
  /ebttrl-verify, is about to say the work is complete, or ebttrl reaches
  the verify phase.
---

# ebttrl-verify

No completion claim without a fresh command in **this** turn.

1. Identify the prove command (project test/build, or the TDD command).
2. Run it fully. Read the exit code and the failure count.
3. If it fails: AUTOHEAL (diagnose → fix → re-run). Do not report green.
4. Quote the command and the result next to the claim.
5. Prefer `ebttrl prove --record` over a hand-typed evidence string.

Not evidence: previous runs, "should pass", agent success reports, linter-only when a test exists.

UI changes: exercise the flow (Safari if web). A screenshot is not verification.

If Superpowers `verification-before-completion` is loaded, follow that file.
