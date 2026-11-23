---
name: workflow-qa-plan
description: "Author an adversarial, black-box QA test plan from an approved contract.md — the boundary, failure-path, and ambiguity cases the dev agent's happy-path TDD skips. Each case is mechanically gradeable and tagged for failure-routing (defect vs contract-ambiguity); unprovable clauses and contract gaps are reported, not guessed. Produces and commits test-plan.md; workflow-qa-test ships it. Does NOT write feature code, write test code, run tests, open a PR, or move the ticket. Use as the QA run's first step, before workflow-qa-test."
argument-hint: "[ABC-123 | project-folder] [--headless]"
---

# QA Test Plan

Write a black-box adversarial test plan against an approved `contract.md`. Assume the implementation is subtly wrong, and design cases that would show where. Someone who doesn't understand the feature must be able to check every case.

Black-box means the plan comes from the contract, never from the implementation: a plan that reads the code stops grading conformance. This skill writes the plan only. No feature code, no test code, no fixes.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`
- `${CLAUDE_SKILL_DIR}/../conventions/worktree-isolation.md`

## What you read

`contract.md` in the project folder (`${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`); none → stop, `/workflow-contract` comes first. `spec.md` and `design.md` for intent only. The tests dev already wrote for this contract. When the contract pins a `## Frontend fidelity source`, the bundle's `design/tokens.css` and `design/spec.md`.

- With a **Lane** in your brief, plan only the behaviors tagged `repo: <lane>`. In a sibling lane, `test-plan.md` lives in your own repo, not beside the read-only contract.
- When `test-plan.md` already exists, amend it: keep every case and `AMB-#` id, add cases for new or changed behaviors, and re-triage each open `AMB-#` against the current contract.
- When the contract's goal is a faster or smaller suite and nothing a user or caller sees changes, write no cases.

## The cases

The plan is **additive**: never re-author what dev's tests already cover. Put the cases where happy-path implementations break: boundary, empty, malformed and oversized inputs; behavior the contract states loosely or leaves implicit; error and failure paths; ordering and state.

Group cases by contract behavior. Every case carries an id, the exact clause it exercises, the setup, one action, the exact expected result, and a pass check that needs **no judgment** ("returns `[]` with status 200", not "handles the empty case gracefully"), asserting only what `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md` *What tests assert* allows. Each also carries a routing tag, which decides who gets a failure:

- `defect` — a failure means the code violates the contract → dev.
- `ambiguity` — the case probes something the contract doesn't pin down → the architect, never dev, who would settle it by guessing.
- `advisory` — a fidelity case: reported, never routed.

For each group, record whether it **gates** (anchored in the contract: a red is a real regression) or is **non-gating** (an ambiguity probe, which would block unrelated work until the contract ratifies it), and the existing test seam or eval tier it belongs in. Tests are filed by seam, not by ticket.

**With a pinned design**, add token cases to each in-scope behavior that renders UI: the running app's computed CSS custom properties equal `design/tokens.css`, with no raw literal where a token applies. Tag them `advisory` and `non-gating`, and keep to the bundle's **Fidelity scope**.

## What you can't grade

- `## Untestable gaps` — clauses with no deterministic check, or checkable only through wording. List them; never fake a check with a string match.
- `## Findings` — clauses where the contract is silent or contradicts itself. Name the ambiguity and the defensible readings, and **don't guess which was meant**. Give each a severity and a one-line reason:
  - `blocking` — the silent input is reachable (a spec flow or an existing caller sends it) **and** the readings give different results that matter: a user doing what the spec describes would plausibly hit it and get what one reading calls wrong, or the choice is costly to reverse after merge because it is persisted, crosses an API boundary, or touches money, permissions or user data. `workflow-qa-test` routes it to the architect.
  - `noted` — anything else: input outside the spec's scope or ruled out by the types, a defensive edge with no caller, or a reachable but rare edge whose answer is cheap to change later. Reported to the human reviewer, never routed, so a trivial gap doesn't cost a pipeline round.
  - `resolved (<contract behavior>)` — on an amended plan, an `AMB-#` the contract now settles.

Headless, nothing is dropped because it seems unlikely: every judgment call becomes a case, a gap or a finding.

## Write and commit

Write `test-plan.md` in the format below and commit it to the working branch, never `main`: a plain commit, no PR and no ticket move.

````markdown
# Adversarial Test Plan: [Feature Name]

**Project:** [folder-name]
**Written against:** contract.md (approved), with spec.md/design.md for intent
**Mode:** black-box — every case must hold for any implementation of the contract.

## Executor notes

[The standard setups a runner reconstructs — fixtures, seams, how a "pass" is observed — so a weak executor needs no feature knowledge.]

## Group [B#] — [contract behavior it targets]

### [id] — [one-line intent]
- **Clause:** [contract clause exercised]
- **Routing:** defect | ambiguity | advisory
- **Setup:** [state/inputs]
- **Action:** [the single action]
- **Expected:** [exact result]
- **Pass iff:** [deterministic check, no judgment]

## Untestable gaps

- **[GAP-#]** — [clause with no deterministic check, and why]

## Findings

- **[AMB-#]** — blocking | noted | resolved ([why]) — [clause the contract leaves silent/contradictory; the defensible readings; the cases that probe it]

## Gating & codification map

| Group | Gating | Home (seam / eval tier) | Cases |
|---|---|---|---|

## Next Steps
- [ ] Codify keeper cases into their seam homes (after the implementation branch exists)
````
