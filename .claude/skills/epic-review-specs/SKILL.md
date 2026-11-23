---
name: epic-review-specs
description: "Review an epic's sub-issue specs as a set for mutual consistency — overlapping/duplicated scope, contradictory boundaries, and cross-slice decisions that should propagate to sibling specs — then interactively edit the specs on the shared epic branch to reconcile them. Reads every slice's spec.md co-located on that branch. Run once an epic's slices are all Spec Done, before /factory-pipeline builds them; headless mode reports conflicts without editing. Use for '/epic-review-specs ABC-123', 'review the epic's specs for consistency', 'reconcile the slice specs'. Not per-slice spec authoring (workflow-questions) or a single-contract review (workflow-review-contract)."
argument-hint: "<epic-ticket-id> [--headless]"
---

# Review Epic Specs

Each of an epic's slices is specced on its own, so the set drifts: two slices claim the same scope, draw a shared boundary two different ways, or a decision settled while speccing a later slice should change an earlier slice's spec. This skill reads the whole set at once, finds those cross-slice inconsistencies, and reconciles them by editing the specs — interactively, one proposed edit at a time, because the specs are already human-approved.

## Required MCPs

- linear

Run the preflight as **Step 0**, before other work, per `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`

## Execution Mode

Detect mode and apply the universal headless rules per `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`.

**Headless specifics for this skill:** **report-only — never edit.** Silently rewriting approved specs is the one thing this skill must not do unattended; an unattended caller (e.g. a pre-build gate) uses this mode as a safe consistency check. Step 2's **Headless** branch has the mechanics.

## Setup

1. **Resolve the epic and its slices.** `mcp__linear__list_issues` with `parentId` = the epic id lists the slices (`get_issue` alone never returns the child list). Halt if the argument's ticket has no sub-issues — it is not an epic.
2. **Check out the epic branch.** `git fetch origin`, then `git switch` to the epic ticket's `gitBranchName` (`mcp__linear__get_issue` on the epic). This is a local interactive branch checkout — worktree-isolation does not apply. No epic branch on `origin` → halt: nothing has been specced.
3. **Locate each slice's spec.** For every slice, resolve `workflows/*-<slice-lowercase>-*/spec.md` per `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`; the epic branch carries them side by side. Note any slice with no spec yet (not Spec Done) — its scope can't be reconciled, so the review is partial; name those gaps. Fewer than two specs present → report that and stop; there is no set to cross-check.

## Step 1: Review the set together

Read every located spec, then judge them against each other for:

- **Overlapping / duplicated scope** — two slices that both own the same requirement, table, endpoint, or surface. Decide which slice should own it; the other cedes or references.
- **Contradictory boundaries** — a boundary one slice puts in scope that another puts out of scope, or the same seam defined two incompatible ways.
- **Cross-slice decisions that should propagate** — a choice recorded in one spec (a data shape, a default, a renamed concept) that silently invalidates an assumption in a sibling spec written before it.

Produce a findings report: each inconsistency, the specs it spans, and the proposed reconciliation. No inconsistencies is a valid outcome — say so and stop without editing.

## Step 2: Reconcile

**Headless** — do not edit. Post the Step 1 findings as a comment on the epic ticket via `mcp__linear__save_comment`, and return them in the summary; make no spec edit, commit, or push, and skip Step 3.

**Interactive** — for each finding, surface the concrete proposed edit(s) and the affected spec(s), and get sign-off (`AskUserQuestion`) before writing — these are approved specs; do not rewrite them silently. On approval, make the **surgical** edit to each affected `spec.md`, preserving everything the finding doesn't touch. A finding the user rejects is dropped; record contested calls nowhere in the spec — they belong in your summary.

## Step 3: Ship the reconciled specs

Only when you edited at least one spec:

- Commit and push per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with **target branch** = the epic branch, **target status** = `none` (commit + push only — no PR, no status move; slices stay Spec Done), staging every edited `spec.md`.
- Comment the reconciliation summary via `mcp__linear__save_comment` on the **epic ticket**, and on each **edited slice ticket** name what changed and why — so a slice owner sees their approved spec moved and by whose decision.

Report: the findings, the specs edited, the pushed commit `<branch>@<sha>`, and any partial-coverage gaps.

## Rules

- **Interactive edits only.** Every spec edit passes through `AskUserQuestion` sign-off; headless never edits.
- **Reconcile, don't re-author.** Resolve the inconsistency with the smallest edit; never expand a slice's scope or rewrite a sound spec.
- **Never touch `main`.** Reconciled specs land on the epic branch; the epic's single PR is `factory-epic`'s.
