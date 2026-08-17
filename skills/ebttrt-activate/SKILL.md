---
name: ebttrt-activate
description: >
  Activate ebttrt on this Mac — plugin, rule, CLI, PATH, and Hoheit wiring.
  Use when the user says "ebttrt aktivieren", "auf einem anderen Mac",
  "ebttrt einschalten", /ebttrt-activate, or asks how to enable the harness
  on a second machine.
---

# ebttrt-activate

Run activate. Do not only explain. Do not invent a GitHub URL.

```bash
python3 "${EBTTRT_ROOT:-$HOME/Developer/ebttrt}/scripts/ebttrt.py" activate
ebttrt doctor
```

If the repo is missing: `git clone https://github.com/maf4711/ebttrt.git ~/Developer/ebttrt` (and optionally `hoheit`), or let `devsync clone` pull `maf4711/ebttrt`. Then run the same command. First time on a Mac is always the python line — the plugin is not linked yet.

`activate` is idempotent: plugin symlink, always-on rule, `~/.grok/bin/ebttrt`, PATH in `~/.zshrc`, plugin enabled, this skill under `~/.grok/skills/ebttrt-activate/`. If Hoheit is found (`$HOHEIT_ROOT` or `~/Developer/hoheit`): `chmod +x` prove/MCP, project MCP `scripts/hoheit-mcp`, user MCP as `${HOME}/…` (never another Mac's home path).

Then: new Grok session or Plugins tab → `r`. Confirm `/ebttrt`. In Hoheit: `scripts/hoheit ebttrt status`.
