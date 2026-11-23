---
name: factory-stage
description: Process one factory pipeline agent's Linear queue (architect, cto, dev, qa, systems-engineer) as the main session — read that agent's Queue config, run every actionable ticket in its trigger status (or just the given ticket ids) through run-stage with workers in parallel worktrees, then move each ticket by its verdict and hand it off (PR, status, comment), and report in chat. Use for '/factory-stage dev', '/factory-stage systems-engineer ABC-123 ABC-124', 'run the dev stage'. For the whole pipeline use factory-pipeline.
argument-hint: "<stage> [<ticket-id>...]"
user_invocable: true
---

# Factory — stage

Run one stage's queue: every actionable ticket in the stage's trigger status goes to a worker, in parallel, and each ticket that comes back `done` is moved on with its PR and a comment. Only a main session can do this, because only it can spawn workers.

## Required MCPs

- `linear`
- `github`

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/run-stage.md`
- `${CLAUDE_SKILL_DIR}/../conventions/stage-verdicts.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`

## Arguments

- `<stage>` — `architect` | `cto` | `dev` | `qa` | `systems-engineer`: the pipeline agent whose queue to process.
- `<ticket-id>...` *(optional)* — only these tickets.

## Queue config

The stage's agent definition, `${CLAUDE_SKILL_DIR}/../../agents/<stage>.md`, carries a **Queue config** section:

- **trigger status** — the Linear status that puts a ticket in this queue.
- **label** *(optional)* — narrows a shared trigger status to this agent.
- **required artifact** *(optional)* — the file that makes a ticket actionable, in its `workflows/<project>/` folder (the one whose name embeds the ticket id). `a.md | b.md` passes when either exists. `none` → no artifact is needed, and the worker's job carries the ticket's title and description instead.
- **worker agent type** — `software-factory:<stage>`.
- **success status** — where a `done` ticket lands when `stage-verdicts.md` maps no verdict for its worker.
- **concurrency** *(optional)* — the most workers in flight at once. Omitted → 6.

## Resolve IDs

- **team** — the `Linear team:` line in the current repo's `CLAUDE.md` or `AGENTS.md`. Missing or ambiguous → halt and name the candidates; never guess, and never use a personal team.
- **project scope** — the `Project:` field beside that line (e.g. `**Linear team:** Acme · **Project:** iOS`), for repos that share a team: project names to include, or `!name` to exclude. No field → every project. A `Factory` ticket is always in scope; a ticket with no project is in scope only when the scope names no includes.

## Lifecycle labels

Two team labels track a ticket through a queue. A label the team hasn't defined is skipped, never fatal.

- `in progress` — a run holds the ticket: a worker is on it, or `factory-pool verify` or `factory-epic finish` is working on it. Every dispatcher skips it, so two runs never take the same ticket. A crashed run leaves it behind for a human to clear. To **claim** a ticket for a step: when it already carries `in progress`, report `held by another run` and stop; else add `in progress`, and drop it when the step ends, whatever the outcome.
- `needs attention` — the ticket stopped short of `done` and waits for a human: a worker was `blocked`, errored or crashed, or a gate failed. The comment says which. The ticket stays in its trigger status, and every queue skips it until a human clears the label.

A ticket that depends on another is not labelled: Linear's `blocked-by` relation says so. The relation outlives the blocker, so read each blocker's status; it is satisfied when the blocker is Done or Canceled.

## Subagent budget

One cap covers every subagent in this session's tree, workers and the subagents they spawn: `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` when set, else 20. A spawn past it is refused and never runs. Count each worker as the subagents it can hold at once, and launch only what fits:

- `architect` — 4: itself plus up to 3 research sub-agents.
- a worker whose agent definition lacks the `Agent` tool — 1.
- a sibling-lane `claude -p` session — 0; it runs in its own process tree.

## Run the queue

A ticket in the trigger status (with the label, when one is set) is **actionable** unless it is:

- labelled `in progress` or `needs attention`;
- a sub-issue: it belongs to `factory-pipeline`, which builds it on its epic branch;
- out of project scope;
- blocked by an unmet blocker.

An actionable ticket without its required artifact is a misconfiguration: report it as an error and don't dispatch it. Never write the artifact yourself.

Run every actionable ticket's stage per `${CLAUDE_SKILL_DIR}/../conventions/run-stage.md`, with `origin/main` as the lane base, up to **concurrency** and the **Subagent budget** at once. Add `in progress` to every ticket before the first launch, so the whole set shows it. `dev` and `qa` get one worker per lane; every other stage one, in the home lane.

run-stage's worktree, branch and fetch commands need the allow entries `Bash(git worktree *)`, `Bash(git -C * worktree *)`, `Bash(git branch -D *)`, `Bash(git -C * branch -D *)` and `Bash(git -C * fetch *)` (`docs/mcp-credentials.md`). A refusal is a provisioning gap to report once, not a failure of each ticket.

## Hand off

Once every lane of a ticket's stage has returned, move the ticket per `${CLAUDE_SKILL_DIR}/../conventions/stage-verdicts.md`. A halted ticket stays where it is. For a ticket that moves, do `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` steps 3–5 yourself on `<gitBranchName>`, with the new status as **target status**: the PR in every lane's repo that has the branch, the status move, and one comment naming every lane's `produced` commit and PR. Then link each entry of an architect hand-back's `depends_on` per `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md` **Link it**. A ticket with `required artifact: none` has no `workflows/` folder, so its PR body carries the worker's `summary` and the ticket URL.

## Report

In chat only. An empty section reads `- None.` **Errors** holds missing artifacts, tickets halted before launch, workers that returned `error`, and crashes.

```
**<Stage> queue — YYYY-MM-DD**

Moved:
- <ticket-id> — <title> → <status>: <summary> (<linear_url>) — PR: <URL per repo>

Blocked:
- <ticket-id> — <title>: <summary>

Errors:
- <ticket-id> — <title>: <summary>
```
