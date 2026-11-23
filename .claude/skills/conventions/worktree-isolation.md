# Convention: Worktree Isolation

How a pipeline worker operates inside the git worktree a dispatcher spawned it in. Governs worktree-isolated runs only; a local interactive session manages its own branch.

## Re-home onto your ticket base first

The isolation mechanism cut your worktree from the **dispatcher's HEAD**, not your ticket's branch. Your brief names both the branch `<gitBranchName>` and its base `<base>`. Before reading or writing anything, re-home onto them:

```bash
git fetch origin
git switch --no-track -C <gitBranchName> <base>
```

`--no-track` keeps the switch from writing upstream config: every worktree of a repo shares one `.git/config`, and sibling workers re-homing at the same moment race for its lock, the loser failing with `could not lock config file`.

If the switch fails because `<gitBranchName>` is already checked out in another live worktree, a prior stage's tree wasn't pruned: stop and report `error`. Never work around it by detaching HEAD and pushing `HEAD:<gitBranchName>` — that silently bypasses this isolation and re-strands the collision for the next worker. Clearing a stranded tree is the dispatcher's job.

**Wrong-base preflight.** Then confirm you landed on the ticket's content: for an artifact stage, the ticket's `workflows/<project>/` folder must resolve via the glob (`resolve-project-folder.md`). If it doesn't, you re-homed onto the wrong base — stop and report `error`.

**A sibling-lane session** — a headless `claude -p` the dispatcher started in a worktree of a sibling repo (`run-stage.md` **Launch**) — is already on `<gitBranchName>`: skip the re-home. Run the preflight (the folder resolves in the home context worktree) and resolve dependencies as below.

## Context worktrees are read-only

Your brief may list **context worktrees**: another repo checked out at the ticket branch, or its base when it has none, so you can see the other side of the change. Reach them only by absolute path, with `Read`, `Grep`, `Glob`, `ls` or `cat`. Never write, commit, or run `git` in one — `git -C` included. Nothing blocks it; you are the only guard. The one exception: run a generator the contract's **Seam** names from the home context (e.g. `npm --prefix <home context> run <script> -- <args>`), with its output in your own tree. The dispatcher creates and removes them; never prune one.

## Write only commands the boundary guard can verify

The worktree-boundary guard rejects a Bash command, burning a turn, when it can't prove from the text alone that it stays in-tree ("too complex to verify that it stays inside the worktree") or when a word in it is on its refused list ("runs a string through `<word>`"). Every Bash call, from the re-home onward, is **one literal command**: a plain command name, literal arguments, paths relative to your cwd.

| The guard rejects | Write instead |
|---|---|
| Chained or piped clauses — `&&`, `\|\|`, `;`, `\|` | One clause per call. |
| Computed values — `$(…)`, backticks, a `$VAR` as the command or a path | Run the inner command alone, then paste its literal output (a sha, a path, a branch) into the next call. |
| Inline code — `node -e`, `npx tsx -e`, `npx … 'import {…}'`, `python -c`, a heredoc piped into an interpreter | A script file in the worktree (below). |
| A refused word anywhere in the command, even quoted or as a path's last segment — `eval source fc coproc trap enable mapfile readarray hash bind complete compgen alias let`, or `.` as the first word. Refused: `npm run eval`, `grep -n "native/complete" <file>`, a verify request to `…/complete`. Only the whole word counts: `npm run eval:errands` passes. | To search: `Grep`, or without it a character class (`grep -n "native/comp[l]ete" <file>`). To run a command that stays in the tree: a `.wt-scratch-<name>.sh` (below), run with `bash`. Never use it for what the guard exists to stop, like git against another tree. |
| File authoring by heredoc — `cat > file <<'EOF'`, `cat >> file <<'EOF'`, `tee -a file <<'EOF'`. Small bodies can pass; code-shaped ones get refused, and a refused heredoc writes nothing. | `Write` for a new file, including `.wt-scratch-*` scripts; `Edit` to change or append. |
| A shell spawned by another command — `bash -c`, `sh -c`, `find … -exec sh -c`, `xargs … sh -c` | `find`'s own predicates (`-name`, `-delete`), or list paths (Glob, or a plain `find`) and act on each in follow-up calls. |
| Wrappers masking the real command — `sudo`, `su`, `runuser`, `env -u VAR` | The underlying command directly. A genuine need for root is an environment problem to report. |
| `cd`, `git -C <path>`, redirects outside the tree | Stay at your cwd; bare `git <subcommand>` with literal args. |

**Logic goes in a script file inside the worktree.** Whenever a step needs a loop, a JSON transform, or a probe that imports a project module, `Write` it to `<worktree-root>/.wt-scratch-<name>.mjs` (or `.ts` / `.sh` / `.py`) and run it as its own call — `node .wt-scratch-<name>.mjs`. Never put it in `/tmp` or a scratchpad: run from there, it can't resolve the worktree's `node_modules`. `rm` it before committing and stage files by explicit path.

**Wait without `sleep` or `Monitor`.** The Bash tool blocks a standalone `sleep N` and points to `Monitor`, which pipeline workers don't have; an inline `until …; do sleep 2; done` is a chain the boundary guard rejects.

- **A command to finish** (suite, build, gate): run it in the foreground with the Bash `timeout` raised, up to `600000` ms — never background it and poll.
- **A condition** (a server started with `run_in_background: true` becoming ready): write a deadline-bounded until-loop that exits non-zero on timeout to `.wt-scratch-wait.sh`, and run `bash .wt-scratch-wait.sh` in the foreground with a Bash `timeout` above that deadline.

**Tool paths are absolute under your worktree root.** `Read` / `Edit` / `Write` take absolute paths: prefix them with `git rev-parse --show-toplevel`'s output, never the shared checkout's root (the repo path in `CLAUDE.md` or the session's primary directory).

## Write shell forms that run on macOS and Linux

Local runs are macOS (BSD coreutils); cloud runs are Linux (GNU). Inspect files with `Read` and search with `Grep` / `Glob`, not `ls` / `cat` / `sed` / `head`; change them with `Edit`, never `sed -i` (`code-writing.md`). When your tool list has no `Grep` / `Glob`, search with `find <dir> -name '<glob>'` and `grep -rn '<pattern>' <dir>`, one literal command per call. When a shell is otherwise unavoidable, write the form both accept:

| Fails on BSD | Write instead |
|---|---|
| An `ls` long option — `ls --color=never` | Plain `ls`. |
| A flag after an operand — `ls <path> -d` | Flags first: `ls -d <path>`. |
| A range with no command — `sed -n 255,335 <file>` | `sed -n '255,335p' <file>`, or `Read` with `offset` / `limit`. |
| A bare in-place flag — `sed -i '<script>' <file>` | `Edit`. If a shell edit is unavoidable: `sed -i.bak '<script>' <file>`, then `rm <file>.bak`. |

An `illegal option`, a `No such file or directory` naming a flag, or a sed `command expected` means a GNU-only form: switch to the tool, don't retry another spelling.

## Resolve dependencies after re-home

A freshly cut worktree has no `node_modules`, and the services your stage exercises may be down. After re-home, whatever your role, before any command that loads the repo's packages, even a probe of `node_modules`, from your cwd:

- **Install deps** — `npm ci` when the repo has a lockfile, skipping cleanly when there's no lockfile or the network is unreachable. Install even when the top checkout has `node_modules` — it reflects `main`, not your branch. Never read or run tooling from another tree's `node_modules`.
- **Ensure runtime services** — `SessionStart` fires only for the top-level session, so nothing starts a shared server (e.g. Postgres) for your worktree. If the repo ships `.claude/hooks/ensure-services.sh`, run `bash .claude/hooks/ensure-services.sh` before any DB-touching command; on a non-zero exit, stop and report the unreachable service. Skip cleanly when the repo ships none.

**Run package-importing code in-tree.** Invoke tools through the repo's npm scripts or `npx <bin>` from your cwd.

**A control whose tool won't resolve is SKIP or BLOCKED, never a raw error.** If a control's tool — or a loader it needs, e.g. `jiti` for a TypeScript ESLint config — still doesn't resolve after install, don't `npm install` it ad hoc unless adding it is your ticket's scope. Report the control BLOCKED when your stage gates on it, SKIP otherwise, naming the missing package as one the repo must declare in `devDependencies`.

## Never print a secret

Your worktree has no `.env`; the app loads the main checkout's `.env` itself at boot. Never read, copy, or symlink it yourself.

Check a secret is set with `test -n "$VAR"`, never by printing it. Don't `printenv`, `echo`, or `printf` a secret or dump the environment (`env`, `printenv`, `set`): the value lands in the run transcript. If the app won't boot for a missing key, report `blocked` naming it: a provisioning gap, never a code defect.

## Never manage worktrees or branches

- Beyond the entry re-home (`git switch --no-track -C <gitBranchName> <base>`), never run `git worktree add`/`remove`/`prune`, `git checkout <branch>`, `git switch` to another branch, or `git branch` create/delete: these collide with a sibling worker's worktree or redirect git to the shared checkout. `ship-artifact.md`'s `git switch <ticket-branch>` names the branch you are already on, so it's a harmless no-op.
- Your git surface is read-only inspection — `git fetch`, `git status`, `git diff`, `git log`, `git rev-parse` — plus `git add`, `git commit`, `git push origin <current branch>`. Never write the shared `.git/config`: no `git push -u` / `--set-upstream`, `git branch --set-upstream-to`, `git config` or `git remote`. Never `git merge`, `rebase`, `reset`, `stash`, or `pull`, except the one `git merge <lane base>` (and its `--abort`) that a lane-base conflict under your brief's **Routed findings** asks dev for.
- Never `ls`, `Read`, write, or remove any `.claude/worktrees/agent-*` path but your own cwd — every other one is a live sibling worker's tree.

## Discover the workflow folder, never construct it

Resolve `workflows/<project>/` by the glob in `resolve-project-folder.md`, never by building the path from a guessed date.
