---
name: workflow-iterate
description: "Amend an existing workflow artifact (design.md or contract.md) with surgical precision, driven by a raw feedback string or a Linear ticket id whose routed QA/architect findings it folds in — then ship the amendment and advance the ticket to the status the change implies. For applying a routed fix to an already-produced artifact, not authoring one from scratch."
argument-hint: "[project-folder | TICKET-ID] [feedback] [--headless]"
---

# Iterate on Workflow Artifacts

Fold feedback into `design.md` or `contract.md` with surgical edits, then ship the amendment and move the ticket to where the change points. Never leave an artifact edited but unshipped.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`
- `${CLAUDE_SKILL_DIR}/../conventions/worktree-isolation.md`

## The feedback

The first argument is a project folder or a Linear ticket id (`${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`). A ticket id is also a source of feedback: the findings, assumptions and open questions earlier stages commented on the ticket. A feedback string passed with it adds to them. Interactive with no feedback: ask what to change. Headless with none: stop and say so.

Tie each finding to the clause it amends, so the change traces back to what triggered it. Question vague feedback, and say when it conflicts with what the artifact already holds.

## The edit

Change only what the feedback requires, with precise edits, and keep what already holds. Interactive: confirm your reading of the change before editing, and check the result with the user after.

- An amended contract still meets every **Contract** line in `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`.
- When an amendment changes what a behavior must do, untick that behavior: `[x]` back to `[ ]`. `workflow-implement` skips ticked behaviors, so an amended one left ticked is never rebuilt.
- In a cross-repo contract, keep each behavior's `repo:` tag, the `## Lanes` dependencies and the Seam true to the amendment, and amend the clause itself: a sibling lane's dev ignores checkboxes and rechecks each behavior against its clause.
- Leave no open question in the artifact that this edit raised.

**A change too big for an edit** — a fundamental design decision, competing patterns to weigh, a scope change that undoes the design — belongs upstream: `/workflow-design`, `/workflow-research` or `/workflow-contract`. Headless, make the edit only when it is safe and unambiguous. Otherwise change nothing and ship nothing, and park a ticket-driven run for a human: comment the needed change and the upstream skill, add the `blocked` label and set the status to `Spec Done`. Under your brief's **Orchestrator mode** line, write nothing to Linear and return `status: blocked` with the same two facts.

## Ship

Hand off per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with the edited file as `artifact`, and the `target status` the amendment implies:

- **the next forward status** (such as `Ready for QA`) — only when the amendment is a pure clarification the current implementation already satisfies, so nothing the implementation does has to change.
- **`Contract Review`** — the amendment changes what the implementation must do, so it goes back through the `cto` gate before dev rebuilds. When unsure, choose this.

In orchestrator mode ship with `target status: none` and return the choice as `route`: `ready_for_qa` or `contract_review`.
