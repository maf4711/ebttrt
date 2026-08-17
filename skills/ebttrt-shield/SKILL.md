---
name: ebttrt-shield
description: >
  Scan the tree for secrets and dangerous commands without printing
  secrets. Use when the user runs /ebttrt-shield, asks for a harness
  security scan, or before shipping agent/hook changes.
---

# ebttrt-shield

```bash
ebttrt shield
ebttrt shield path/to/file
```

The CLI prints path, rule, and severity. It does **not** print secret values.

Grades: A clean, B medium, C high, F critical (private keys, cloud keys, GitHub PATs).

Also blocked live by the PreToolUse hook: `dump-keychain`, `rm -rf /`, cookie-theft libs, force-push to main/master, `DROP DATABASE`.

Do not run `security dump-keychain`. Do not loop `security find-*-password -w`. Do not read Chrome Safe Storage. Keychain access is targeted and one item at a time.
