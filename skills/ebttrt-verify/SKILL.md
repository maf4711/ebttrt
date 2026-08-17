---
name: ebttrt-verify
description: >
  Evidence before any done/fixed/passing claim. Use when the user runs
  /ebttrt-verify, is about to say the work is complete, or ebttrt reaches
  the verify phase.
---

# ebttrt-verify

No completion claim without a fresh command in **this** turn.

1. Identify the prove command (project test/build, or the TDD command).
2. Run it fully. Read the exit code and the failure count.
3. If it fails: AUTOHEAL (diagnose → fix → re-run). Do not report green.
4. Quote the command and the result next to the claim.
5. Prefer `ebttrt prove --record` over a hand-typed evidence string.

Not evidence: previous runs, "should pass", agent success reports, linter-only when a test exists.

UI changes: exercise the flow (Safari if web). A screenshot is not verification.

If Superpowers `verification-before-completion` is loaded, follow that file.
