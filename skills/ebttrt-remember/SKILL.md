---
name: ebttrt-remember
description: >
  Bind a finished loop to exact source state and store an instinct.
  Use when the user runs /ebttrt-remember, /ebttrt-receipt, or ebttrt
  reaches the remember phase.
---

# ebttrt-remember

After verify is green, close the loop. Do not remember failures as wins.

```bash
ebttrt prove --record
ebttrt done
```

That writes a receipt (cwd, HEAD, dirty paths, dirty_digest) and clears the active loop. HEAD alone is not identity when the tree is dirty.

If a pattern should survive this repo, also:

```bash
ebttrt remember "durable sentence"
ebttrt improve
```

Remember needs a MATCH receipt (or `--force`). First hit stays at confidence 0.5; the second hit on the same sentence earns it. `improve` lists only earned instincts. Do not store secrets, tokens, home paths, or medical details. One sentence per instinct.
