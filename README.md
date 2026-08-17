# EBTTRT

<p align="center">
  <img src="docs/slogan.jpg" alt="Even Better Than The Real Thing" width="720">
</p>

**Even Better Than The Real Thing**

| E | B | TT | R | T |
|---|---|---|---|---|
| Even | Better | Than The | Real | Thing |

Grok-native agent harness. Thin loop, on-demand skills, receipts, shield.
Not an ECC / Everything-Claude clone.

```
consult → begin → plan|test|implement → review → prove --record → done
```

## Better than Everything Claude

[Everything Claude Code](https://github.com/affaan-m/ECC) wins the catalog:
hundreds of skills, agents, and a hard test gate on every turn.

EBTTRT wins the *loop* — less context, proof that actually ran, memory that
has to be earned.

| | Everything Claude | EBTTRT |
|---|---|---|
| Context | Dump the catalog | One short rule + ≤1.8k inject |
| Skills | 200+ always nearby | 10, one at a time |
| Tests | Block every turn | One Stop-nudge; `prove` runs itself |
| Done | Chat says so | Fresh prove on this HEAD / dirty digest |
| Review | Prompt, maybe | `review.json` gates multi-file / public API |
| Memory | Store the win | First hit 0.5; second + two receipts to improve |
| Receipts | Optional notes | MATCH or DRIFT against the tree |
| Install | Heavy checkout | `activate` is idempotent, no foreign `/Users/…` |
| Product AI | Mixed in | Hoheit stays Mistral; this is the coding loop |

Use ECC if you want a second operating system. Use EBTTRT if you want the
agent to finish *this* change and prove it.

## What we still make smarter

Not more skills. These four:

1. **Prove quality** — default chain is tests, then types/lint when those exist. `"prove": "true"` stays a warning.
2. **Review sees hunks** — `review.json` must carry `git diff` (not the plan chat). Revise+high still blocks `done`.
3. **Fail that teaches** — last fail as one sanitized line in the 1.8k card. No journal paste.
4. **Instincts decay** — unused stays 0.5; unused+stale drops. Improve never invents a skill.

Public 1.0 adds CI (`ebttrt eval` on every push) and a real clone URL.
Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md).

## Install

```bash
git clone https://github.com/maf4711/ebttrt.git ~/Developer/ebttrt
python3 ~/Developer/ebttrt/scripts/ebttrt.py activate
ebttrt doctor
```

Grok plugin only:

```bash
grok plugin install maf4711/ebttrt@v1.0.0
# still run activate if you want PATH, the always-on rule, and Hoheit wiring
python3 ~/.grok/plugins/ebttrt/scripts/ebttrt.py activate
```

Optional PIM: `git clone https://github.com/maf4711/hoheit.git ~/Developer/hoheit` then activate again.

Overrides: `$EBTTRT_ROOT`, `$HOHEIT_ROOT`. User MCP is `${HOME}/…`, never another Mac's home.

New Grok session (or `r` in Plugins). `/ebttrt-activate` is a no-op if already ok.

This Mac, repo already here:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/ebttrt.py activate
```

## Use

```bash
ebttrt consult "add OAuth"
ebttrt begin "add OAuth"
ebttrt prove --record
ebttrt done
ebttrt receipt check
```

In Grok: `/ebttrt add OAuth login`

Project prove override:

```json
{ "prove": "python3 -m unittest discover -s tests -q" }
```

Or a chain: `["cmd1", "cmd2"]`. Discovery if you skip the file: `package.json` `scripts.test`, `cargo test`, `go test ./...`, pytest, `make test`, `tests/test_*.py`.

## Uninstall

```bash
ebttrt uninstall
```
