---
name: ebttrt-tdd
description: >
  Test-first for a behavior change. Use when the user runs /ebttrt-tdd,
  asks for TDD, or ebttrt reaches the test phase.
---

# ebttrt-tdd

Behavior changes get a failing test first. Do not write production code until the test fails for the right reason.

1. Write the smallest failing test (or use the project's existing runner).
2. Run it. Confirm **red**. If it is already green, the test does not prove the change — fix the test.
3. Implement the minimum that turns it green.
4. Re-run the same command. Confirm **green**.
5. Keep the exact command; `ebttrt-verify` will run it again later.

Skip TDD only for pure docs, comments, or config with no behavior.

If Superpowers `test-driven-development` is loaded, follow that file instead of duplicating it here.
