---
name: verify
description: Verify a change at the app's real surface and report one verdict - PASS, FAIL, SKIP or BLOCKED. Use for "/verify", "verify this change", or when a factory skill asks for the repo's verify over a tree and diff range.
argument-hint: "[<tree path>] [<diff range>] [<evidence ticket>]"
---

# Verify

Run one command and report what it prints:

```bash
bash .dev/verify.sh <tree path>
```

`<tree path>` is the worktree named in the arguments, or `.` when none is given. The command drives the app in that tree and prints one line, `VERDICT: <PASS | FAIL | SKIP | BLOCKED> — <reason>`. Report that verdict and reason exactly. Run nothing else, and never substitute your own check.
