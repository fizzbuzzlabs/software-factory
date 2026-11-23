---
name: workflow-qa-test
description: "Codify an approved test-plan.md into real tests in the repo's existing seam files / eval tiers, run them against the implementation, and report a triaged red/green result. A correctly-written adversarial test that goes red is a finding (routed defect→dev, ambiguity→architect), never forced green. Writes test code only — no feature code. Use after workflow-qa-plan, once the implementation exists."
argument-hint: "[ABC-123 | project-folder] [--headless]"
---

# QA Test Codification

Turn the cases in `workflows/<project>/test-plan.md` into committed tests, run them against the real implementation, and report what passed and what didn't.

Success is every case correctly codified, not every test green. A red on a correctly written test is a **finding**. Never edit the implementation, and never weaken or delete the test, to turn it green: that ratifies the bug this suite exists to catch. This skill writes test code only.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`
- `${CLAUDE_SKILL_DIR}/../conventions/worktree-isolation.md`

## What you read

`test-plan.md` in the project folder (`${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`); none → stop, `/workflow-qa-plan` comes first. `contract.md` for the clauses. The implementation and the tests dev already wrote; no implementation → stop. With a **Lane** in your brief, codify and run only that lane's cases, in your own repo.

## Codify

Write each case as a test in the seam file or eval tier the plan names, never in a file of its own per ticket. Follow the repo's test idioms and `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`. Stay **additive**: codify the plan's cases and never re-author a test that exists.

- A gating case goes in the gating suite.
- An ambiguity probe goes in a non-gating tier or behind a skip or expected-fail marker whose reason states the open question in words, not its `AMB-#`, so an assertion nobody ratified can't block an unrelated PR.
- An `advisory` fidelity case is a token check (computed CSS custom properties equal `design/tokens.css`), also outside the gating suite.
- A case whose only check is wording isn't codified as a string match. List it under **Untestable** in the report.

When the plan has no cases, mutation-check the tests the ticket rewrote and any non-test code it added, per `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md` *Why-tests*, and add the smallest assertion to an existing test only where a mutation survives.

## Run

Run the codified tests, then the full suite.

- **Green** — make sure it isn't green for nothing: mutation-check it per *Why-tests*.
- **Red** — decide why. A miscoded test is fixed and re-run. A red because the implementation violates the contract, or because the contract is silent, is a finding: leave the test as written.

Then run the repo's typecheck and lint (the commands `${CLAUDE_SKILL_DIR}/../workflow-implement/SKILL.md` *Static gate* names) and any tests that check the suite itself. Draft PRs skip CI, so your own test code must pass all of it on your final tree; fix it without loosening config. Report failures that aren't yours.

## Route

The **ambiguity findings** are the surviving ambiguity reds plus every open `blocking` `AMB-#` in the plan's `## Findings`, red test or not: its probe is skipped, so it can't go red. A `noted` or `resolved` `AMB-#` is never a finding.

A ticket has one status, so the findings become one decision, ambiguity first, because while the contract is unsettled "correctly fixed" has no meaning and dev could only guess:

- **Any ambiguity finding** → the architect: `Spec Done`.
- **Else any defect finding** → dev: `Ready for Dev`.
- **Else** → forward: `In Review`.

`advisory` findings never change the route.

## Ship and report

Hand off per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: code` and the status above as `target status`. Under your brief's **Orchestrator mode** line, ship with `none`, make no status move, and return the decision as `route` (`in_review` / `ready_for_dev` / `spec_done`) with the findings in your hand-back.

Commit the codified tests, red finding tests included, so each failing test travels with its finding. The trace from case id to test title lives in the commit message, with the greens' mutation checks, and in the ticket comment (in orchestrator mode, your hand-back's `findings` and `summary`, which the dispatcher posts). That comment carries every finding as id, `test file › title` (or `test-plan.md` for a blocking `AMB-#` with no red test), contract clause, defect or ambiguity, and one line; dev finds the red test from it. Noted `AMB-#`s are listed apart.

Close with this report:

````markdown
## QA test report: [project]

**Codified:** [N] cases → [files touched]
**Untestable (not codified):** [id — clause checkable only through wording, or none]
**Green:** [N] (mutation-checked)
**Reds fixed as test bugs:** [N]
**Findings (surviving reds):**
- [id] — [test file › title] — [contract clause] — defect → dev: [one line]
- [id] — [test file › title | test-plan.md (blocking AMB)] — [contract clause] — ambiguity → architect: [one line]
**Noted ambiguities (non-routing):**
- [AMB-#] — [why noted] — [one line]
**Advisory (fidelity, non-routing):**
- [id] — [token] — expected [X], got [Y]
**Full suite:** [pass | fail — detail]
**Typecheck / lint:** [pass | fail — detail | not defined by the repo]
**Routed to:** [Ready for Dev | Spec Done | In Review]
**PR:** [url | none — Orchestrator mode]
````
