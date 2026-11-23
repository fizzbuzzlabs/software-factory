You're a headless session in a git worktree of `{lane}`, already on your ticket branch `{branch}` — your cwd is its root. Don't re-home. Run the wrong-base preflight and resolve its dependencies, per `{worktree_isolation}`. If the `auto`-mode classifier denies a step your job needs (a push, a simulator command, a verify step), don't skip it: hand back `blocked`, naming the denied command in `summary`. End your final message with your hand-back as one JSON object on its own last line.

Work only inside your cwd: `Read`/`Edit`/`Write` paths are absolute under it, never the shared checkout's. Commit and push on your ticket branch only — beyond the re-home, never run `git worktree`, `git checkout`, `git switch` or `git branch`, and never touch a `.claude/worktrees/agent-*` path but your cwd.

A boundary guard rejects every Bash command it can't statically prove stays in-tree, costing a turn per retry, so make each call one literal command: no `&&` / `;` / `|` chains, no `$(…)` or computed values, no inline code (`eval`, `node -e`, `npx … '<code>'`, `bash -c`), no `cd` / `git -C` / out-of-tree redirects. When a step needs logic, write a script file into the worktree and run it there — never from `/tmp`, where it can't resolve the worktree's `node_modules`. Never wait with `sleep` or `Monitor`: run an awaited command in the foreground with a raised Bash `timeout`, and wait for a condition by running `bash .wt-scratch-wait.sh` holding a deadline-bounded until-loop.

Hand back `status` (`done`, `blocked` or `error`), `summary`, `produced` — the pushed commit `<branch>@<sha>`, a commit URL when formable — and `worktree` — the absolute path you ran in — plus the fields your agent definition adds.

**Orchestrator mode.** Ship with `target status: none` (`ship-artifact.md`): commit and push your branch, open no PR, make no Linear move or comment. Return your full hand-back, including `verify` and any `verify_blocked_reason` (dev) or `route` and `findings` (qa).

Run your job over workflows/<project>/ for {ticket}.
