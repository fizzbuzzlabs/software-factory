---
name: workflow-contract
description: "Define behavioral contracts from approved design. Produces contract.md with ordered behaviors, module boundaries, and testing decisions, then commits it to the ticket's branch and moves the ticket to Contract Review. Use after design is complete, before implementation."
argument-hint: "[ABC-123 | project-folder] [--headless]"
---

# Behavioral Contract

Turn the approved design into a behavioral contract: what the system must do, ordered by how much risk each behavior removes. Each behavior becomes one test-first cycle during implementation. Outside its **Footprint** and **Seam**, a contract has no file paths, no line counts and no code.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`
- `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`

## What you read

In the project folder (`${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`): `design.md` and `research.md`, read in full yourself, and `design/spec.md` when a `design/` bundle exists. Find how the codebase already does what the design chose (`codebase-pattern-finder`) before you write.

Interactive: warn when `design.md` or `research.md` is missing; when `contract.md` already exists, show its Behaviors and Modules and ask whether to refine it or start fresh; and agree the behaviors, the module boundaries and each testing decision with the user before writing. Headless: decide all of it yourself, note a missing input under `## Open Questions`, and record each contested call (ordering, mock boundaries, the integration and unit split) under `## Assumptions`. `## Open Questions` is only for what you truly cannot decide.

## What the contract must hold

- **Behaviors** — each one outcome a user or caller sees, with a sentence on what it proves and why it sits where it does in the order. They, and the rest of the contract, meet every **Contract** line in `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`, which also sets their order.
- **Modules** — each module's responsibility and how callers use it, as deep modules: a lot of behavior behind a simple interface. Describe the idea, not the file structure.
- **Testing decisions** — what is tested through public interfaces, where the mock boundary is, the integration and unit split, and prior art from `research.md`.
- **Anti-behaviors** — from the design's Boundaries and the spec's "Won't Have".

Three rules bind the testing decisions:

- **Seam rule** — a behavior that involves a user interaction or crosses a network or process boundary names an at-the-seam acceptance test: one that dispatches a real interaction or makes a real HTTP or process call. A view-tree-only or pure-function-only test doesn't satisfy it.
- **Observability rule** — a behavior that can reject or silently drop a user's action names how that becomes observable, and the reason it gives. Name the reason, never the mechanism. This covers what a user can trigger, not internal guards.
- **Assertion rule** — a testing decision names only assertions `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md` *What tests assert* allows.

## Lanes

When your brief lists context worktrees, the ticket may land in several repos: this one (the home repo) and the siblings listed. A separate worker builds each repo's behaviors, seeing only this contract and the other repo's code.

- Tag every behavior `repo: <name>` with the one repo it lands in. A behavior that needs two repos is two behaviors.
- In `## Lanes`, list each tagged repo with what it `depends on`: another lane whose pushed change it consumes, else `none`. A dependent lane's dev waits, so mark a dependency only when one exists.
- Write the **Seam**: exactly where the lanes meet. Wire shapes field by field, shared source files, generated files and the command that regenerates them.

Check every claim about a sibling against its code in your context worktree.

## Footprint

List every file the behaviors will create or change, tests included, in every repo the ticket lands in (`${CLAUDE_SKILL_DIR}/../factory-pipeline/SKILL.md` **Conflicting tickets** reads it):

- One bullet per repo: its name in backticks (the home repo's `origin` name, or the sibling's name), a colon, then each path or glob relative to that repo's root, backticked and comma-separated. `*` matches within one path segment, `**` across segments.
- Follow a file with `(additive)` when the ticket only adds entries to a list or registry in it, such as `tool-registry.ts`.
- Leave out what never counts as overlap (`${CLAUDE_SKILL_DIR}/../factory-pipeline/SKILL.md` **Conflicting tickets**).

Name the narrowest glob that covers the change. Too wide holds back tickets that would never conflict; too narrow lets a conflict through to the test merge after dev.

## Write and ship

Write `workflows/<folder>/contract.md` in one pass, in this format:

```markdown
# Contract: [Feature/Task Name]

**Project:** [folder-name]
**Created:** YYYY-MM-DD
**Design:** design.md

## Behaviors

Ordered by risk-reduction. Each is one TDD tracer bullet.

1. [ ] **[Behavior]** `repo: <name>` — [User/caller-facing outcome. No file paths. No code. Tag only with lanes.]

## Lanes

[Only with lanes.]

- **<repo>** — depends on: <repo> ([what it consumes]) | none

**Seam:** [Wire shapes, shared and generated files, the regenerate command.]

## Footprint

- `<repo>`: `<path or glob>`, `<path>` (additive)

## Modules

### [Module name]
**Owns:** [responsibility]
**Interface:** [how callers interact — conceptual, not code]

## Testing Decisions

- [Public interface testing approach]
- [Mock/stub boundaries]
- [Prior art from research]

## Frontend fidelity source

In-scope behaviors must satisfy the frozen design bundle's `spec.md` **Fidelity scope** (`workflows/<folder>/design/`). Pinned node(s): [id,…]. `contentHash.tokens`: [hash]. Omit when no `design/` bundle exists.

## Anti-Behaviors

- [Things this must NOT do]

## Assumptions

- [A call made without asking, and why. Already decided — reversible on review.]

## Open Questions

- [Only what this stage could not decide and a human must answer. Omit the section when there are none.]

## Next Steps
- [ ] `/workflow-implement [folder-name]`
```

Hand off per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: contract.md`, `target status: Contract Review` (`none` under your brief's **Orchestrator mode** line), staging `design.md`, `research.md` and the `design/` bundle with it. The `cto` stage reviews the shipped contract; never start a review from here. End with the link to the shipped contract.
