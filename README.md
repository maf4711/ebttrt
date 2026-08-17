# EBTTRT

**Even Better Than The Real Thing**

| E | B | TT | R | T |
|---|---|---|---|---|
| Even | Better | Than The | Real | Thing |

ECC dumps hundreds of skills into context and blocks every turn until tests pass. ebttrt keeps one short rule, tracks one open loop, **runs the prove command itself**, nudges once if you claim done without it, and binds receipts to HEAD **or** a dirty-tree digest.

```
consult → begin → plan|test|implement → review → prove --record → done
```

## 0.8 — quality gates

Prove can be a command **chain**. `done` needs a fresh passing prove. Multi-file
changes need `ebttrt review`. Instincts start at 0.5 and only `improve` after a
second hit + two receipts. Session inject is ≤1.8k (journal stays on disk).
Doctor checks VERSION = plugin.json = code, and that the plugin is a symlink
to this repo.

## 0.3 — what actually got better

| Before | Now |
|---|---|
| You typed evidence by hand | `ebttrt prove` finds and runs the project tests |
| `done` needed a pasted string | `done` reuses a **fresh** prove (same HEAD + dirty_digest) |
| Context card was a static note | SessionStart / PreCompact try `additionalContext` **and** write the card |
| Receipts were write-only | `ebttrt receipt check` reports MATCH or DRIFT |
| Memory was ebttrt-only | Closing a loop appends `## ebttrt` to Grok `MEMORY.md` if that dir exists |
| No audit trail | Per-workspace `journal.jsonl` |

Project override (this repo ships one):

```json
{ "prove": "python3 -m unittest discover -s tests -q" }
```

Discovery if you skip the file: `package.json` `scripts.test`, `cargo test`, `go test ./...`, pytest, `make test`, `tests/test_*.py`.

## Why not ECC

- Ten skills, one at a time (`/ebttrt-activate` turns the harness on)
- One Stop-nudge on a done-claim — not a permanent test gate (`EBTTRT_STOP_NUDGE=0` disables it)
- Composes with Superpowers, Ruflo, project `AGENTS.md`
- Shield never prints secrets; live-blocks `dump-keychain`, `rm -rf /`, cookie theft, force-push to main

Quality next: [docs/ROADMAP.md](docs/ROADMAP.md) (prove → earned instincts → review gate → thin context → reproducible activate). Not a skill catalog.

## Install

This Mac (already have the repo):

```bash
python3 -m unittest discover -s tests -q
python3 scripts/ebttrt.py activate
```

## Other Mac

Private repo (`maf4711/ebttrt`). Clone, then activate. `repo-sync` / `devsync clone` also picks it up.

```bash
git clone https://github.com/maf4711/ebttrt.git ~/Developer/ebttrt
# optional PIM wiring
git clone https://github.com/maf4711/hoheit.git ~/Developer/hoheit

python3 ~/Developer/ebttrt/scripts/ebttrt.py activate
ebttrt doctor
```

Overrides: `$EBTTRT_ROOT`, `$HOHEIT_ROOT`. User MCP is written as `${HOME}/…`, never another user's `/Users/…`.

New Grok session (or `r` in the Plugins tab). Then `/ebttrt-activate` is a no-op if already ok.

## Use

```bash
ebttrt consult "add OAuth"
ebttrt begin "add OAuth"
ebttrt prove --record
ebttrt done
ebttrt receipt check
```

In Grok: `/ebttrt add OAuth login`

## Uninstall

```bash
ebttrt uninstall
```
