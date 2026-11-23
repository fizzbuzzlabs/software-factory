---
name: workflow-quick
description: "Take a small, well-understood feature — typically a one-line Linear ticket — straight to contract.md in a single pass, with no spec.md, research.md, or design.md. Fills in the blanks itself, commits the contract to the ticket's branch, and moves the ticket to Contract Review; it never implements. Route anything with real requirements discovery or design tradeoffs to /workflow-questions instead."
argument-hint: "[ABC-123 | feature description] [--headless]"
---

# Quick Contract

Collapse the `questions → research → design → contract` pipeline into one pass for a feature small enough that the four artifacts would cost more than they teach. Produces `contract.md` — plus a frozen `design/` bundle when the run references a paper.design — and none of the intermediate `spec.md` / `research.md` / `design.md` artifacts.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`

## Execution Mode

Detect mode and apply the universal headless rules per `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`.

**Headless specifics for this skill:** skip Step 4 entirely — resolve every blank with best judgment and log each under `## Assumptions`.

## Steps

### 1. Resolve the input

The argument is either a Linear identifier (`ABC-19`) or a plain feature description. For a ticket, read its title, description, and project. A one-line ticket is the whole spec — the blanks are yours to fill, not the user's to dictate. A plain description has no ticket yet — you'll create one at save time (Step 5), so every quick contract is ticket-anchored.

### 2. Size gate

Stop and route to `/workflow-questions` — passing the ticket id or the raw feature description, since no folder exists yet — if any of these hold, naming which one fired:

- more than ~5 behaviors
- a user-facing product decision with no defensible default
- a new module boundary, dependency, or external integration
- a data-model or migration change

A small feature extends a pattern the codebase already has. Anything else earns the full pipeline.

### 3. Scan for prior art

Run `codebase-locator` and `codebase-pattern-finder` in parallel, then read the files they name. Findings feed the contract's `## Context` directly — write no `research.md`.

### 4. Fill the blanks

Ask at most five questions via **AskUserQuestion**, reserved for blanks where a wrong guess would waste the implementation. Every remaining call is yours to make and log under `## Assumptions`.

### 5. Write the contract

**Resolve the ticket first.** A passed-in identifier → reuse it. A plain description → create it now by invoking the `create-ticket` skill (Skill tool), never `save_issue` directly, once the contract's contents exist to infer a project from: title = the feature topic, description = a summary plus the `contract.md` path.

Save to `workflows/YYYY-MM-DD-<ticket-lowercase>-<slug>/contract.md`, naming the folder with the resolved ticket id, in the format defined by the Step 5 template in `workflow-contract/SKILL.md`, with two deltas:

- Replace the `**Design:**` field with `**Source:**` — the ticket URL.
- Add a `## Context` section above `## Behaviors`: at most five lines on what exists today and what changes. It stands in for the absent `research.md` and `design.md`, which `/workflow-implement` would otherwise reach for.

If the feature has a UI and the run references a paper.design URL, and `paper` is reachable, invoke `workflow-freeze-design` (`../workflow-freeze-design/SKILL.md`) with that URL and `--folder workflows/<folder>` before writing the contract — else skip (`paper` stays out of this skill's Required MCPs). Then, if `workflows/<folder>/design/` exists, fill the contract's **Frontend fidelity source** section from `design/spec.md`'s provenance; omit it otherwise.

The behaviors carry every obligation any other contract's do — the Seam rule and the Observability rule in `workflow-contract/SKILL.md` apply unchanged, and so does every **Contract** line in `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`. This pass drops the artifacts, never the obligations: being small makes a behavior no cheaper to get wrong, and a silent rejection no easier to debug.

### 6. Hand off

Hand off per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: contract.md`, `target status: Contract Review`, staging the `design/` bundle alongside it when present. Print the behaviors and assumptions. Then stop — `cto` reviews it from `Contract Review`, then `dev` builds it from `Ready for Dev`.

## Rules

- Never write `spec.md`, `research.md`, or `design.md`.
- Never implement or commit production code — it commits only `contract.md` and, when present, the `design/` bundle, via the ship handoff.
- Every run is ticket-anchored — reuse a passed-in ticket or create one from a plain description (Step 5) — so the ship handoff always moves a real ticket to Contract Review.
