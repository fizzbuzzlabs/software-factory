# Pipeline guide

How tickets move from spec to review once a repo is [set up](setup.md). The
[`factory-pipeline`](../.claude/skills/factory-pipeline/SKILL.md) skill has the exact rules.

## Spec, then build

You spec each ticket. `/workflow-questions <ticket>` writes `spec.md` and moves it to Spec Done;
`/workflow-quick <ticket>` goes straight to `contract.md` and Contract Review.

Then run `/factory-pipeline` in a main session. Each stage's agent works in the background, and
every ticket moves to its next stage the moment its own checks pass, until nothing is ready.
`/factory-pipeline ABC-12 ABC-13` drives only those tickets.

| Status | Agent | Moves it to |
|---|---|---|
| Spec Done | `architect` (research → design → contract) | Contract Review |
| Contract Review | `cto` (reviews and fixes the contract) | Ready for Dev |
| Ready for Dev | `dev` (TDD, then verify in the running app) | Ready for QA |
| Ready for QA | `qa` (adversarial tests) | In Review, or back to Ready for Dev (a bug) or Spec Done (a gap in the spec) |

## Review

A QA-green ticket stacks onto the `review-pool` branch, behind a single `review-pool → main` PR
and a review ticket that lists what to check in the app for each one. Nothing merges to `main`
without you. `/factory-pool remove <ticket>` takes one back out.

## Epics

A bigger feature goes in an epic: a ticket whose sub-issues (slices) build on one shared branch
and land together as the epic's own PR. Spec each slice, run `/epic-review-specs <epic>` to make
the specs agree, then `/factory-pipeline <epic>`. Merge an epic PR with a merge commit, not a
squash or rebase.

## What holds a ticket back

- **Blockers.** A ticket waits until its `blocked-by` tickets are done. Spec and research add
  that link when a ticket builds on code another unmerged ticket adds.
- **Overlapping code.** Each contract lists the files it expects to change. Two tickets that
  overlap never run dev at the same time, and a branch that conflicts with the work ahead of it
  goes back to dev.
- **A stuck ticket.** A worker that's blocked or errors, or a ticket that keeps bouncing between
  dev and QA, gets the `needs attention` label and a comment saying why. Fix the cause and remove
  the label; the next run picks it up.

## One stage at a time

`/factory-stage <agent>` works one queue: `architect`, `cto`, `dev`, `qa` or `systems-engineer`.
Each ticket it moves gets its own PR to `main` instead of joining the review pool. It's also how
the `systems-engineer` queue runs (`Todo` tickets with that label), since `/factory-pipeline`
doesn't cover it.

## Apps split across repos

With a `Sibling repos:` line in `CLAUDE.md`, dev and QA run once per repo the contract touches,
and each repo gets its own pool or epic PR.
