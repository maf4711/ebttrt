# ebttrt quality roadmap

Quality = a claim is true, bound to source, and cheap to check.
Not more skills. Not a second ECC.

Baseline: **0.8.0** — Q1–Q5 shipped in one cut (prove chain, earned instincts,
review gate, 1.8k inject, version/symlink doctor). Always-on rule stays under 30 lines.

## North star

A finished loop has:

1. A prove command that actually ran on **this** tree.
2. A receipt bound to HEAD **or** dirty_digest.
3. A review that saw the **diff**, not the plan chat.
4. Memory only if the same win happened twice **and** the receipt still MATCH.

If a change does not move one of those four, it is out of scope.

## Non-goals

- ECC catalog (200+ skills, 60 agents)
- Permanent test gate on every turn
- Cross-IDE OS (Claude / Cursor / Codex)
- Own orchestrator next to Ruflo
- Growing `rules/ebttrt-loop.md` into a playbook

Reuse Superpowers, Ruflo, project `AGENTS.md`. Promote only earned instincts.

---

## Phase Q1 — Prove is evidence (0.4 → in 0.8)

**Gap:** `prove` runs one command. `done` trusts a fresh last-prove.
A green `echo ok` or a stale-but-matching digest still ships.

**Do**

- `.ebttrt.json` may list `prove` as string **or** `["cmd1", "cmd2"]` (tests, then types/lint).
- Refuse `done` if last prove is missing, failed, or tree digest drifted.
- Record each command’s argv, exit, digest, duration. No secret stdout in receipts.
- `consult` names the prove chain, not a vibe.

**Done when**

- Unit tests: multi-command prove, stale digest blocks `done`, empty prove config still discovers.
- A workspace with only `"prove": "true"` fails doctor/consult with a warning, does not block if the user set it on purpose.
- `ebttrt eval` stays green.

## Phase Q2 — Instincts must be earned (0.5 → in 0.8)

**Gap:** `ebttrt remember` appends anything. Improve *says* “twice”; the CLI does not check.

**Do**

- `remember` requires an open loop **or** `--force`, and a MATCH receipt for this workspace.
- Dedup near-identical instinct text (same workspace). Second hit raises confidence; first stays ≤ 0.5.
- `improve` lists only instincts with confidence ≥ 0.5 **and** two receipts. It does not invent skills.
- Instinct text is one durable sentence. No paths that look like secrets.

**Done when**

- Tests: first remember stays low confidence; duplicate + second MATCH receipt promotes; unmatched receipt rejected.
- `instincts` shows count, confidence, workspace — not a dump of the session.

## Phase Q3 — Review sees the diff (0.6 → in 0.8)

**Gap:** Review is a skill prompt. Verdict does not gate `remember`. Same-session bias is optional.

**Do**

- `ebttrt review` writes `review.json` (verdict, findings, diff-stat, source digest).
- `remember` / `done` refuse if last review is `revise` with critical/high, or digest drifted since review.
- One-file fix may skip review (already allowed). Multi-file or new public API may not.
- Skill stays short: spawn `ebttrt-reviewer`, grade the diff, write the file. No rewrite-in-review.

**Done when**

- Tests: revise+high blocks done; approve + same digest allows; dirty tree after review is drift.
- Review artifact contains file hunks or `git diff --stat`, never the plan narrative.

## Phase Q4 — Context that lands (0.7 → in 0.8)

**Gap:** SessionStart `additionalContext` is unreliable. The card can grow toward 6k.

**Do**

- Hard cap **1.8k** on injected context (active loop, last prove OK/FAIL, one receipt line).
- Full card stays on disk (`ebttrt context`). Hooks never paste the journal.
- Stop-nudge once, then silent. No second sermon.
- Doctor reports whether the last session wrote a card, not whether Grok displayed it.

**Done when**

- Tests: inject ≤ 1800 chars with an active loop + 20 journal lines; disk card still complete.
- No SessionStart path writes instincts or full journal into the model.

## Phase Q5 — Reproducible activate (0.8)

**Gap:** Other Mac = clone `maf4711/ebttrt` (private) then `ebttrt activate`. Receipts still cannot name a released ebttrt until there is a tag.

**Do**

- Git history + version tag for ebttrt. `activate` still works from a copy.
- Receipts store `ebttrt` version (already) **and** plugin path digest.
- `doctor` fails if plugin symlink ≠ discovered repo, or VERSION ≠ `plugin.json`.
- Still no invented public URL. Remote only if you add one.

**Done when**

- `activate` twice is a no-op. Doctor green on a second `$GROK_HOME`.
- A tagged tree’s `VERSION` matches doctor output.

---

## Order and size

| Phase | Version | Why this order |
|---|---|---|
| Q1 Prove | 0.4 | Every later gate sits on a real prove |
| Q2 Instincts | 0.5 | Memory without prove is fanfic |
| Q3 Review | 0.6 | Needs prove + source digest |
| Q4 Context | 0.7 | Thin card after the loop is trustworthy |
| Q5 Activate | 0.8 | Ship the quality loop, then the install story |

One phase at a time. Each phase: tests first, then CLI, then the matching skill (no new catalog entries except a command that already has a skill).

## Quality bar (every phase)

- Stdlib only. Files under 500 lines.
- Shield still never prints secrets.
- `python3 -m unittest discover -s tests -q` green.
- `grok plugin validate .` green.
- Rule file not longer than now.
- Skill count may grow by **at most one** (only if a phase needs a slash entry that is not a prompt essay).

## Out of this roadmap

Hoheit product AI, Ruflo swarms, Safari/Keychain (already user rules), meister-style Homebrew. Those stay outside the harness.
