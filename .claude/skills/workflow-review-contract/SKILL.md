---
name: workflow-review-contract
description: "Review a drafted contract.md at the Contract Review gate — module boundaries, risk-ordering, completeness, scope-vs-spec drift, testability — editing contract.md / design.md / research.md in place to resolve what the review finds, then shipping to the ticket's branch and advancing the ticket to Ready for Dev. Fixes rather than blocks. Use after the contract ships to Contract Review, before implementation; unlike workflow-iterate, it conducts its own critique rather than folding in an externally-routed fix."
argument-hint: "[ABC-123 | project-folder] [--headless]"
---

# Review Contract

Give the drafted contract a technical-leadership pass before dev builds it, and fix what falls short in place. Fix, don't block: there is no changes-requested or parked outcome.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`
- `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`
- `${CLAUDE_SKILL_DIR}/../conventions/worktree-isolation.md`

## Review and fix

Read `contract.md` in the project folder (`${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`), with `spec.md`, `design.md` and `research.md` for intent. No contract → stop; it isn't drafted yet.

Judge it on:

- **Module boundaries** — deep modules behind simple interfaces. Fix leaky coupling and any shallow module that only forwards.
- **Change principles** — every **Contract** line in `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md` holds.
- **Completeness** — every behavior and anti-behavior the spec and design imply is there, including a requirement the draft dropped. Nothing is there that they don't intend.
- **Testability** — a tester can reduce every clause to a deterministic check, and no testing decision asks for an assertion `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md` *What tests assert* forbids.
- **Footprint** — meets `${CLAUDE_SKILL_DIR}/../workflow-contract/SKILL.md` **Footprint**, checked against the code. A contract without one gets one.
- **Lanes** *(when your brief lists context worktrees)* — per `${CLAUDE_SKILL_DIR}/../workflow-contract/SKILL.md` **Lanes**: each behavior is tagged with the one repo it lands in, each `depends on` is real, and the Seam is exact enough for each lane's worker to build its side alone. Check every claim about a sibling against its code.

Edit `contract.md` to resolve what you find, and `design.md` or `research.md` too when the cause is upstream, so the three stay consistent. Make surgical edits and keep what already holds. A contract that needs no change is a valid outcome: change nothing and say so. Headless, record each contested call under `## Assumptions`.

## Ship

- **You edited something** — ship per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: contract.md`, `target status: Ready for Dev`, staging every file you edited.
- **You edited nothing** — there is nothing to commit. Move the ticket from Contract Review to Ready for Dev and post your approval as a comment.

Under your brief's **Orchestrator mode** line, make no Linear move or comment either way: ship edits with `target status: none`, or just return `done`.

End with a summary: what you reviewed, the edits you made or that none were needed, the pushed commit, and any assumptions.
