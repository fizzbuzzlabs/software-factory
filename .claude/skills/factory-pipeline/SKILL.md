---
name: factory-pipeline
description: "Run factory-pipeline, the conveyor belt that moves every ready ticket (Spec Done → Contract Review → Ready for Dev → Ready for QA) to its next stage the moment its own gates pass, with workers in the background so a slow ticket never holds up a fast one; stacks each QA-green standalone ticket onto the shared review pool (factory-pool) and each QA-green epic sub-issue onto its epic branch (factory-epic); ends by verifying the pool and finishing completed epics. Use for '/factory-pipeline', '/factory-pipeline ABC-123 ABC-124', 'run the conveyor belt'. Not one stage's queue on its own (factory-stage)."
argument-hint: "[<ticket-id>...]"
user_invocable: true
---

# Factory pipeline

You are the dispatcher. One run takes every ticket that is ready for a stage and keeps each one moving, architect → cto → dev → qa, until nothing is ready and nothing is running. Workers do each stage's work in the background and hand back a verdict; you launch them, move the tickets, and integrate what comes out green. No ticket waits on another unless Linear says it is blocked by it.

## Required MCPs

- linear
- github

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md`
- `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/run-stage.md`
- `${CLAUDE_SKILL_DIR}/../conventions/stage-verdicts.md`

## Arguments

- `<ticket-id>...` *(optional)* — drive only these tickets; an epic's id stands for its sub-issues. Omitted → every ready ticket.

## What you work with

- **Team, project scope, labels** — per `${CLAUDE_SKILL_DIR}/../factory-stage/SKILL.md` (**Resolve IDs**, **Lifecycle labels**).
- **Stages** — `architect`, `cto`, `dev`, `qa`. Each one's **Queue config** in `${CLAUDE_SKILL_DIR}/../../agents/<stage>.md` gives its trigger status, required artifact and worker agent type.
- **Lanes and sibling repos** — per `${CLAUDE_SKILL_DIR}/../conventions/run-stage.md` (**Repos and lanes**). Halt before anything else if a sibling's local path isn't a checkout of the repo `CLAUDE.md` names.

A ticket is one of three kinds:

- **Standalone** — no parent, no sub-issues. Its lane base is `origin/main`. QA-green, it joins the review pool.
- **Epic sub-issue** — has a parent. Its lane base is the epic branch, `origin/<parent gitBranchName>`, in each lane's repo; without that branch on the home `origin`, skip it. A sibling repo that lacks the epic branch gets it pushed from its `origin/main` before the first worker needs it. QA-green, it merges into the epic branch.
- **Epic** — has sub-issues. Never built itself.

## When a ticket is ready

All of:

- It sits in a stage's trigger status, in project scope, without `in progress` or `needs attention` (**Lifecycle labels**), with no worker in flight, and hasn't halted this run. When this run itself clears what halted a ticket (resolves its conflict, renumbers its clashing file), drop `needs attention`: the ticket rejoins this run and its next stage launches.
- Its blockers are met (**Lifecycle labels**), and for an epic sub-issue so are its epic's. One exception: a sibling slice of the same epic counts once it is In Review, because by then it is merged into the epic branch. So a standalone ticket blocked by a pooled one waits for the pool PR to merge, and a ticket blocked by an epic waits for the epic PR to merge. A blocked ticket is looked at again after every return.
- For `dev`, it is still unblocked after the **Epic gate** and the **Footprint gate** (**Conflicting tickets**).
- The stage's required artifact is on the ticket's **base** (`${CLAUDE_SKILL_DIR}/../conventions/run-stage.md` **What the dispatcher supplies**), in `workflows/*-<ticket-lowercase>-*/`. For `qa`, the ticket branch also exists in every lane's repo. A missing artifact is a misconfiguration: halt the ticket. Never write one yourself.

## Run it

First, before any launch, `/factory-epic sync <epic-id>` for every epic in project scope (with `<ticket-id>`s, only the epics they name or are slices of) that isn't Done or Canceled and has its branch on the home `origin`.

Then run every ready ticket's stage per `${CLAUDE_SKILL_DIR}/../conventions/run-stage.md`, as many at once as the **Subagent budget** in `${CLAUDE_SKILL_DIR}/../factory-stage/SKILL.md` allows. `architect` and `cto` get one worker per ticket; `dev` and `qa` one per lane. As each worker returns, move its ticket per `${CLAUDE_SKILL_DIR}/../conventions/stage-verdicts.md`, query every stage's trigger status in Linear again (within the run's `<ticket-id>`s, when given), and launch whatever is now ready, without waiting for the others. A ticket created, moved or unlabelled since the run started joins it this way.

- **architect `done` with `depends_on`** — move the ticket, then link each entry per `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md` **Link it**.
- **qa `route: in_review`** — a standalone ticket moves to **In Review**, then `/factory-pool add <ticket-id>`. A sub-issue isn't moved: `/factory-epic merge <ticket-id>` merges it and moves it.
- **A sub-issue's `architect` and `cto` briefs** carry the epic's description, in a fenced block under the heading **Epic context (cross-cutting rules, binding on this slice)**, with one line saying these rules win over the slice's `spec.md` where they conflict.
- **dev `done`, PASS or SKIP in every lane** — run the **Test merge** (**Conflicting tickets**) before moving the ticket.
- **A defect round** re-runs dev, then qa, only in the lanes that routed a defect, each brief carrying that lane's findings under **Routed findings**. A conflict round, from the test merge or a lane-base conflict (`${CLAUDE_SKILL_DIR}/../conventions/run-stage.md` **Before the launch**), re-runs dev only in the lanes that conflicted.
- **An epic-verify round** — `/factory-epic finish` reports a verify FAIL traced to one slice as `defect` or `ambiguity`. Move the slice per `${CLAUDE_SKILL_DIR}/../conventions/stage-verdicts.md`, with the failure under **Routed findings** in its next brief; a defect re-runs only the lane of the repo that failed.
- **Rounds** — a ticket gets at most 2 defect or ambiguity rounds per run, epic-verify ones included; after that, halt it. A conflict round spends none. Halt it sooner when a round returns the same route with the same findings as the round before (qa's or epic verify's): another round would buy the same answer.
- **Port-busy** — a dev hand-back with `verify_blocked_reason: port-busy` spends no round: retry or halt it per `${CLAUDE_SKILL_DIR}/../conventions/run-stage.md` **Port-busy**.

**Halting a ticket** — `needs attention` per **Lifecycle labels**; for a round halt, the comment carries the last findings.

## Conflicting tickets

Two tickets that would change the same code never run dev at the same time, and neither do two such epics. Three checks find such a pair, and each ends the same way for the one that waits: a `blocked-by` the other, which the readiness rule enforces, and one comment per blocker, the footprint and epic gates' first, the test merge's second. An epic's entry carries its slice: `` `<entry>` (<SLICE-ID>) ``.

```
**Blocked by <BLOCKER-ID>** — footprints overlap in `<repo>`:
- `<this ticket's entry>` ↔ `<blocker's entry>`

**Blocked by <BLOCKER-ID>** — branches conflict in `<repo>`:
- `<path>`
```

- **In flight** — every ticket in project scope at Ready for Dev, Ready for QA, or In Review with its branch not yet in `origin/main`, except epics, the pool's review ticket and the ticket being checked.
- **Which one waits** — the one less far along: In Review, then Ready for QA, then Ready for Dev with `in progress`, then Ready for Dev waiting; at the same point, the newer by `createdAt`. Against a standalone ticket, a slice is as far along as its epic's furthest slice, and at the same point the standalone waits. A pair already related by `blocked-by`, either way round, gets nothing new; a relation to an epic covers its slices.
- **Only a sibling slice waits on a slice.** Any other ticket that waits on one is blocked by the slice's epic instead.
- **Never overlap** — `workflows/`, a file `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md` **Resolve conflicts** regenerates or renumbers, and a file every footprint involved marks `(additive)`: `integrate-branch` resolves those at the pool or epic merge.

**Footprint gate** — before a ticket's dev launch, read the `## Footprint` (`${CLAUDE_SKILL_DIR}/../workflow-contract/SKILL.md` **Footprint**) of its `contract.md` and of each in-flight ticket's, from `origin/<gitBranchName>` in the home repo. Two entries overlap when they name the same repo and some path matches both. Each in-flight ticket with an overlap gets the move above, whichever of the pair waits. A contract with no `## Footprint` touches nothing: the gate never holds it or anything against it, and the test merge after dev catches its conflicts. Slices of one epic are checked against each other like any two tickets. A standalone ticket is checked against each building epic's footprint in place of that epic's slices'.

**Epic gate** — an epic's **footprint** is the union of its slices' footprints, each from the slice's `contract.md` on `origin/<slice gitBranchName>`; a slice with no contract there yet adds nothing. An epic is **building** while it isn't Done or Canceled and a slice of it is at Ready for Dev with `in progress`, Ready for QA or In Review. Before a slice's dev launch while its epic isn't building, compare the epic's footprint with every building epic's. Each that overlaps gets the move above with this epic waiting: the `blocked-by` and the comment go on the epic itself, and the readiness rule holds all its slices. Epics reaching this gate in the same pass go oldest `createdAt` first, so the newer one waits. The slice's own footprint gate runs next.

**Test merge** — in each lane's repo, test-merge the ticket's branch with `git merge-tree --write-tree` against `origin/review-pool`, when the pool is live (`${CLAUDE_SKILL_DIR}/../factory-pool/SKILL.md` **Is there a live pool?**), and against the branch of every in-flight ticket at Ready for QA or In Review. Ready for Dev branches get their own test merge when their dev returns. A conflict confined to paths that never overlap clears. Any other is a conflict round (`${CLAUDE_SKILL_DIR}/../conventions/stage-verdicts.md`), with the move above and this ticket waiting. Its blocker is the other ticket or, for the pool tip, every entry whose merge changed a conflicting path (its `Pool-Ticket` trailer).

## Close out

Once nothing is ready and nothing is running:

- If this run added to the pool, `/factory-pool verify`.
- For each epic that had a sub-issue merge this run, `/factory-epic finish <epic-id>`. A FAIL it traces to one slice is an epic-verify round (**Run it**), so the run goes on; close out again once it is empty.
- When the session can watch a PR's CI and fix its failures (the desktop app's Auto-fix), turn that on for every pool and epic PR this run opened. Never turn on auto-merge.

## Routine steps

Take these without asking, and list each under **Done for you** in the report:

- the merges `factory-epic sync` and `${CLAUDE_SKILL_DIR}/../conventions/run-stage.md` **Before the launch** make;
- relaunching a ticket whose halt this run cleared, and an epic-verify round;
- each `blocked-by` **Conflicting tickets** or an architect's `depends_on` adds, and each conflict round;
- turning on CI Auto-fix;
- filing follow-up work a worker or verify turned up but that lies outside its ticket: to Backlog, through `create-ticket` (Skill tool).

The run's closing question is only for a real decision: a product or design choice, or a halted ticket these rules can't move.

## Report

One rollup in chat, never posted to Linear. An empty section reads `- None.` Read CI from each PR's checks without waiting for it; a run still going reports as `started`.

**In progress elsewhere** comes from Linear as the report is written: every ticket in project scope labelled `in progress` that this run isn't working on, pool review tickets and epics included. A ticket this run passed over for that label is listed there, not under **Skipped**.

```
**Factory pipeline — YYYY-MM-DD** (<all tickets | ticket-id, ...>)

Moved:
- <ticket-id> — <title>: <stages run, e.g. architect → cto → dev → qa> → <final status> — PRs: <one URL per repo the ticket touches>

Review pool: <added ticket-ids> — <PR URL per repo> — verify <verdict per repo | held by another run> — CI <pass | fail | started>
Epics: <epic-id>: <merged sub-issues> — <PR URL per repo | not finished | held by another run | halted: reason> — CI <pass | fail | started>

Done for you:
- <ticket-id | epic-id> — <step, e.g. merged origin/main into the epic branch | renumbered migration 0049 → 0050 | sent back to dev after epic verify | blocked by ABC-N: footprints overlap | blocked by ABC-N: relies on its code | sent back to dev: lane-base conflict | Auto-fix on PR #N | filed follow-up ABC-N>

Waiting on blockers:
- <ticket-id | epic-id, for all its slices> — blocked by <blocker-id> (<blocker status>)

Halted:
- <ticket-id> — <stage>: <reason>

Skipped:
- <ticket-id> — <reason>

In progress elsewhere:
- <ticket-id> — <title>: <status>, last updated <YYYY-MM-DD HH:MM> (<age, e.g. 3h ago>)
```

## Rules

- Run in the main session; invoke `factory-pool`, `factory-epic` and `create-ticket` with the Skill tool, never through a subagent.
