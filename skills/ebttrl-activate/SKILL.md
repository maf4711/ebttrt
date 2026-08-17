---
name: ebttrl-activate
description: >
  Activate ebttrl on this Mac — plugin, rule, CLI, PATH, and Hoheit wiring.
  Use when the user says "ebttrl aktivieren", "auf einem anderen Mac",
  "ebttrl einschalten", /ebttrl-activate, or asks how to enable the harness
  on a second machine.
---

# ebttrl-activate

Run activate. Do not only explain. Do not invent a GitHub URL.

```bash
python3 "${EBTTRL_ROOT:-$HOME/Developer/ebttrl}/scripts/ebttrl.py" activate
ebttrl doctor
```

If the repo is missing: `git clone https://github.com/maf4711/ebttrl.git ~/Developer/ebttrl` (and optionally `hoheit`), or let `devsync clone` pull `maf4711/ebttrl`. Then run the same command. First time on a Mac is always the python line — the plugin is not linked yet.

`activate` is idempotent: plugin symlink, always-on rule, `~/.grok/bin/ebttrl`, PATH in `~/.zshrc`, plugin enabled, this skill under `~/.grok/skills/ebttrl-activate/`. If Hoheit is found (`$HOHEIT_ROOT` or `~/Developer/hoheit`): `chmod +x` prove/MCP, project MCP `scripts/hoheit-mcp`, user MCP as `${HOME}/…` (never another Mac's home path).

Then: new Grok session or Plugins tab → `r`. Confirm `/ebttrl`. In Hoheit: `scripts/hoheit ebttrl status`.
