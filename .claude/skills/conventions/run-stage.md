# Convention: Run Stage

One pipeline stage for one ticket, as a main-session dispatcher (`factory-pipeline` or `factory-stage`) runs it: get the ticket's branch ready, launch the worker, and clean up after it.

The worker only commits and pushes; it never opens a PR or moves the ticket. Neither does this procedure: the dispatcher moves the ticket, per `stage-verdicts.md`.

## Repos and lanes

- **Home repo** — the repo the dispatcher runs in, named by its `origin` repo name (`<owner>/<repo>` → `<repo>`). Every ticket's `workflows/<folder>/` (`spec.md`, `research.md`, `design.md`, `contract.md`) lives here.
- **Sibling repos** — the home `CLAUDE.md`'s `Sibling repos:` line: comma-separated `<name> (<local path>, <owner>/<repo>[, check: <workflow file>])`. `check` names a home-repo workflow that compares the home branch against that sibling. No line → home is the only repo, and nothing below about siblings or context worktrees applies.
- **Lane** — a repo the ticket's code lands in, on the same branch name (`gitBranchName`) in every repo. The lanes are the repos `contract.md`'s behaviors are tagged with (`repo: <name>`; untagged is home's; a tag naming neither home nor a sibling halts the ticket). `architect` and `cto` run once per ticket, in the home repo; `dev` and `qa` run once per lane, in that lane's repo.
- **Lane order** — the contract's `## Lanes` section marks a lane that `depends on` another. Its dev starts only once that lane's dev has returned `done` and pushed. Independent lanes run in parallel.

The home repo's checkout is the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), even when the session runs in a linked worktree; a sibling's is its local path.

## What the dispatcher supplies

- **ticket** — id, title, `gitBranchName`, current labels.
- **worker** — the agent type from the stage agent's **Queue config**.
- **lane** — the repo this worker runs in; home for `architect` and `cto`.
- **lane base** — the branch the lane's work lands on, in the lane's repo: `origin/main` for a standalone ticket, `origin/<epic gitBranchName>` for an epic sub-issue.
- **base** — what the worker starts from: `origin/<gitBranchName>` when that exists on the lane's `origin`, else the lane base.
- **job** — `Run your job over workflows/<project>/ for <ticket-id>.`; for a worker whose Queue config has `required artifact: none`, `Work <ticket-id> — <ticket title + description>.`
- **context** *(optional)* — blocks appended to the brief verbatim, such as **Epic context** or a lane's **Routed findings**.

## Before the launch

Leave the ticket so a worker can start on `<gitBranchName>` in the lane's repo. Anything else here that can't be done halts the ticket: no launch, `needs attention`, and a comment saying what was found.

Every merge here runs in a scratch worktree, never in a checkout someone works in. Merge, never rebase or force-push: an open PR must keep its history.

- **No stale tree holds the branch.** A worktree a crashed run left on `<gitBranchName>` in the lane's repo blocks the worker's re-home. Remove it, and the local branch with it, when that loses nothing: no uncommitted or untracked files, no commits `origin/<gitBranchName>` lacks, and no process running in it. Otherwise leave it; the ticket halts, and the comment names the tree and what removing it would lose.
- **The branch contains its lane base.** When `origin/<gitBranchName>` exists and is behind the lane base, merge the lane base into it and push. A conflict only in derived or generated files is resolved per `integrate-branch.md` **Resolve conflicts**, then pushed. Any other conflict is a **lane-base conflict**. Before an architect or cto launch, it halts the ticket. Before a dev or qa launch, leave the branch as it was, add no `needs attention`, and comment:

  ```
  **Lane-base conflict** — merging `<lane base>` into `<gitBranchName>` conflicts in `<lane>`:
  - `<path>`
  Dev merges it and resolves.
  ```

  Before a dev launch, launch anyway, with `Lane-base conflict: merging <lane base> into <gitBranchName> conflicts in <path>, <path>.` under the lane's **Routed findings**. Before a qa launch, don't launch: the ticket goes back to Ready for Dev (`stage-verdicts.md`), where its dev launch meets the same conflict.
- **Context worktrees** *(with siblings)* — read-only checkouts of the other side, so a worker can see it: every sibling for `architect` and `cto`; for `dev` and `qa`, every other lane, plus the home repo for a sibling lane. Each sits at `<ctx repo>/.claude/worktrees/context-<ticket-lowercase>-<stage>-<lane>`, detached at the first of `origin/<gitBranchName>`, that repo's lane base and `origin/main` to exist there. When a sibling lane depends on home, install the home context's dependencies too: the lane's generators and verify server run from it.
- **Label the ticket** — add `in progress`, if it isn't there yet.

## The brief

`<worktree-isolation>` is the absolute path of this convention's sibling `worktree-isolation.md`; a worker can't resolve a bare filename under a plugin install.

A home-lane brief opens:

> You're isolated in your own git worktree — your cwd is already its root (`git rev-parse --show-toplevel` to confirm). It was cut from the dispatcher's HEAD, not your ticket's branch. Before reading or writing anything, re-home it onto your ticket base: `git fetch origin`, then `git switch --no-track -C <gitBranchName> <base>` — never `git reset`, and never drop `--no-track` (tracking writes the `.git/config` sibling workers share). Then run the wrong-base preflight and resolve its dependencies, per `<worktree-isolation>`.

A sibling-lane brief opens instead:

> You're a headless session in a git worktree of `<lane>`, already on your ticket branch `<gitBranchName>` — your cwd is its root. Don't re-home. Run the wrong-base preflight and resolve its dependencies, per `<worktree-isolation>`. If the `auto`-mode classifier denies a step your job needs (a push, a simulator command, a verify step), don't skip it: hand back `blocked`, naming the denied command in `summary`. End your final message with your hand-back as one JSON object on its own last line.

Every brief then carries the worker rules:

> Work only inside your cwd: `Read`/`Edit`/`Write` paths are absolute under it, never the shared checkout's. Commit and push on your ticket branch only — beyond the re-home, never run `git worktree`, `git checkout`, `git switch` or `git branch`, and never touch a `.claude/worktrees/agent-*` path but your cwd.
>
> A boundary guard rejects every Bash command it can't statically prove stays in-tree, costing a turn per retry, so make each call one literal command: no `&&` / `;` / `|` chains, no `$(…)` or computed values, no inline code (`eval`, `node -e`, `npx … '<code>'`, `bash -c`), no `cd` / `git -C` / out-of-tree redirects. When a step needs logic, write a script file into the worktree and run it there — never from `/tmp`, where it can't resolve the worktree's `node_modules`. Never wait with `sleep` or `Monitor`: run an awaited command in the foreground with a raised Bash `timeout`, and wait for a condition by running `bash .wt-scratch-wait.sh` holding a deadline-bounded until-loop.
>
> Hand back `status` (`done`, `blocked` or `error`), `summary`, `produced` — the pushed commit `<branch>@<sha>`, a commit URL when formable — and `worktree` — the absolute path you ran in — plus the fields your agent definition adds.

Then the stage part:

> **Orchestrator mode.** Ship with `target status: none` (`ship-artifact.md`): commit and push your branch, open no PR, and make no Linear status move or handoff comment. Verify evidence is exempt: pass `verify` `--ticket <ticket-id>`, and let it land the recorder's video comment and its `.log` attachments on your ticket, whatever the verdict. Keep the recording until its upload is confirmed. Return your full hand-back, including `verify` and any `verify_blocked_reason` (dev) or `route` and `findings` (qa).
>
> **Lane: `<lane>`** — build and test only the contract behaviors tagged `repo: <lane>`. *(dev and qa, when the home repo has siblings)*
>
> **Context worktrees** — read by absolute path; never write, commit or run git in them: *(when any were opened)*
> - `<repo>` at `<ref>`: `<path>`
>
> <job>
>
> <context, if any>

## Launch

**Home lane** — `Agent(subagent_type=<worker>, isolation: "worktree", run_in_background: true)` with the brief. Launch every worker that is ready in one message. If `<worker>` doesn't resolve, try once more without its `software-factory:` prefix.

**Sibling lane** — an `Agent` worker's worktree is always cut from the dispatcher's repo, so the dispatcher starts a headless session in the sibling itself:

- Its worktree is `<repo>/.claude/worktrees/agent-<ticket-lowercase>-<stage>`, on `<gitBranchName>` from `<base>`. The `agent-` prefix makes the repo's per-worker tooling (a per-worktree simulator, say) treat it as a worker tree.
- In that tree, as one background Bash call: `<env> claude -p --agent <dev | qa> --permission-mode auto --output-format json "<brief>" < /dev/null`. Nobody can answer a permission prompt in `-p`, so `auto` has a classifier decide each action. Never `bypassPermissions`: an auto-mode dispatcher refuses to launch it.
- `<env>` is empty unless the lane depends on home. Then it points the sibling's `ensure-services` at a server started from the home context on a per-ticket port, `4000 + (<ticket number> mod 1000)`, through the variables the sibling's `.claude/hooks/ensure-services.sh` reads for the home checkout and its API URL — e.g. `APP_DIR=<home context> API_BASE_URL=http://localhost:<port>`. Stop whatever a crashed run left on that port first; `ensure-services` would serve it silently.
- Stdout is one JSON object, and the hand-back is the last line of its `result`. Treat it as `error` when the exit is non-zero, `is_error` is true, `subtype` isn't `success`, the last line doesn't parse, or the session outlives the stage's budget (dev 4h, qa 2h; stop it).

## After a worker returns

Given the worker's hand-back, or nothing when it crashed:

- **Clean up what the launch made.** The worker's worktree, the branch it was created on (the Agent result's `worktreeBranch`, not the ticket branch the tree has checked out since the re-home), a local `<gitBranchName>` that matches `origin`, this worker's context worktrees, and any home-branch server. Leave a crashed sibling session's tree for the next launch's stale-tree check.
- **Pair a sibling lane that pushed.** A standalone ticket's sibling lane gets a draft PR against `main` if it has none, its body linking `https://github.com/<home owner>/<home repo>/tree/<gitBranchName>/workflows/<folder>`. An epic sub-issue's lane gets no PR: its code reaches `main` through the epic PR, and a PR into the epic branch would be marked merged by `factory-epic merge`'s push, which makes Linear move the slice to Done. When the sibling's `Sibling repos:` entry names a `check`, re-run that workflow's latest run on the home branch (`gh run rerun`; the GitHub MCP has no Actions tools): a `pull_request` check re-runs only on pushes to its own repo, so it still shows the sibling as it was.
- **Labels and comment.** A dev `blocked` with `verify_blocked_reason: port-busy` goes to **Port-busy** instead. Otherwise drop `in progress` once no other worker of the ticket is in flight. Then:
  - any other `blocked`, an `error`, or a crash gets `needs attention` and the comment below;
  - a `done` gets the comment only when the hand-back carries assumptions, open questions, qa findings, or `noted` ambiguities in qa's summary, or when it is a dev `done` missing its verify evidence. Orchestrator mode skips the worker's own handoff comment, so this is their only record, and dev reads a routed defect from it.

**Verify evidence.** For a dev hand-back with `verify` PASS or FAIL, from a lane whose `.claude/skills/verify/SKILL.md` uses `verifier-web` (the only recorder that lands evidence; skip the check for any other lane), look on the ticket for evidence created since the launch: a comment opening `📹` (`mcp__linear__list_comments`) or an attachment (`mcp__linear__get_issue`). With neither, the comment's **Findings** carries `⚠️ No verify evidence on the ticket — verify <verdict>, nothing landed`.

The comment renders only what the worker handed back, plus that evidence line. ` (<lane>)` appears only when the home repo has siblings; after a crash `<summary>` is the dispatcher's own account.

```
**<worker> (<lane>) — <done | blocked | error> — <YYYY-MM-DD>**

Produced: <branch>@<sha>
Worktree: <worktree>

<summary>

**Assumptions** — decided; later stages build on them, so check them at review.
- <entry>

**Open Questions** — unresolved; need an answer.
- <entry>

**Findings**
- <entry>
```

Hand the dispatcher `{ ticket, worker, lane, status, verify?, verify_blocked_reason?, route?, findings?, depends_on?, produced, summary }`.

## Port-busy

A dev hand-back with `verify_blocked_reason: port-busy` found the app's ports taken: a clash over a resource, not a fault in the ticket. The ticket keeps `in progress` and gets no comment, so no other run takes it while it waits. Launch that lane again once every dev worker that ran alongside it has returned. When none did, the port is held outside this run, by another run's verify say: wait 5 minutes first, with a background `sleep 300`. The ticket's third port-busy return in one run halts it instead: drop `in progress`, add `needs attention`, and comment as for any other `blocked`.
