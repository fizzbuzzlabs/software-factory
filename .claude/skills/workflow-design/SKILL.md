---
name: workflow-design
description: "Iterative design conversation to build shared understanding before contracting behaviors. Produces design.md. Use when the user wants to discuss architecture, make design decisions, choose between competing approaches, or align on a technical direction — especially after research is complete."
argument-hint: "[ABC-123 | project-folder] [--headless]"
---

# Design Conversation

Build a shared design concept before any behavior is contracted. Per Brooks, a shared design concept predicts downstream quality more than any single artifact.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`

## What you read

`spec.md` and `research.md` in the project folder (`${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`), in full, yourself. Where research found competing patterns, design is where one wins. Don't re-research here: a gap in the research is named, and the human decides whether to run `/workflow-research` again.

## Decide

A design is done when these are decided:

- **Pattern choice** — which codebase patterns to follow.
- **Scope boundaries** — what is in, and what is explicitly out.
- **Key tradeoffs** — simplicity against flexibility, and the like.
- **Anti-goals** — what this must not do.
- **Module boundaries** — where the complexity lives and what the interfaces look like.

**Interactive:** surface your understanding so the human can correct it, not a polished proposal. Be wrong out loud. Start with a brain dump (the problem, the current state, the constraints, the competing patterns and which you lean toward, and what you're unsure of). Then grill: one pointed question at a time, each with 2–4 options and their tradeoffs, your recommendation first, forcing an explicit decision. Ask one question too many before one too few. Name a missing `spec.md` or `research.md` and ask whether to go on; show an existing `design.md` and ask whether to refine it or start fresh.

**Headless:** decide every item yourself, with the reasoning in `design.md`: each decision under **Key Decisions**, each call you would have asked about under `## Assumptions`, and a missing input under `## Open Risks`.

## Write and ship

Write `workflows/<folder>/design.md` in one pass. The Design Concept is the part contract and implement key off.

```markdown
# Design: [Feature/Task Name]

**Project:** [folder-name]
**Created:** YYYY-MM-DD

## Design Concept
[2-3 paragraphs: what we're building and the key insight — the one idea everyone
 working on this should hold, readable on its own by someone new to the project.]

## Key Decisions
[Numbered list of decisions made during the design conversation.
 Each entry: the decision, the rationale, and alternatives considered.]

1. **[Decision]** — [rationale]. Considered [alternative] but rejected because [reason].

## Chosen Patterns
[Which existing codebase patterns we're following and why.
 Reference specific file:line examples from research.]

## Boundaries
[What this design explicitly does NOT cover.
 Where the boundaries are between this work and adjacent systems.]

## Open Risks
[Known unknowns that contract/implementation should account for.]

## Next Steps
- [ ] Create contract: `/workflow-contract [folder-name]`
```

Hand off per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: design.md`, `target status: none`, staging `research.md` with it, and end with the link to the shipped design.
