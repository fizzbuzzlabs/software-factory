---
name: workflow-questions
description: "Interactive thought partner for exploring ideas and clarifying requirements. Reads a Linear ticket or creates one from the idea, produces spec.md, then commits it to the ticket's branch and moves the ticket to Spec Done."
argument-hint: "[ABC-123 | feature idea or problem to explore] [--headless]"
---

# Turning Ideas Into Requirements

Interview the user to understand their idea, then write a `spec.md` covering the **what** and **why**.

## Required MCPs

- linear

Run the preflight as **Step 0**, before any other work, per `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`

## Execution Mode

Detect mode and apply the universal headless rules per `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`.

**Headless specifics for this skill:** skip the interview entirely. Derive the spec from the provided idea plus a repo scan. Resolve each requirements fork (users, triggers, boundaries, scope) with best judgment and YAGNI, logging each under `## Assumptions`. Still read or create the Linear ticket; when the team or project can't be resolved unambiguously, pick the best match and log it under `## Assumptions` rather than blocking.

## Artifacts

- **Reads**: user input or a Linear ticket (title, description, project, comments), CLAUDE.md, git history
- **Produces**: `spec.md`, plus a new Linear ticket when the input was a plain idea

## What This Skill Does NOT Do

Architecture, data models, APIs, technical choices, solution alternatives, error handling, testing, or data flow — those belong in `/workflow-design`.

## Setup

Strip any mode token, then resolve the argument to one of three inputs:

1. **Existing workflow folder** (e.g. `2026-01-30-abc-123-feature`) — look for `workflows/[argument]/` and read `spec.md` if present (resuming).
2. **Linear identifier** (e.g. `ABC-123`) — call `get_issue` and read its title, description, project, and comments. This ticket is the interview seed and the write-back target; its existing project carries through to the spec, so no project inference is needed at save time. **If it has a `parentId`** (an epic sub-issue), also `get_issue` the parent and read the epic's description and goals: this ticket is one slice of that epic, so the epic frames its problem, its scope boundaries, and how it fits alongside sibling slices — carry that framing into the interview and the spec.
3. **Plain idea** — no ticket yet. You'll create one at save time, once the spec's contents exist to infer a project from.

If the input already carries clear, detailed requirements, offer to skip the interview and go straight to writing the spec.

## Interview

Scan the repo first (CLAUDE.md, related code, recent commits) to ask informed questions.

Walk down each branch of the requirements tree — who uses it, what triggers it, the boundaries, what's out of scope — without crossing into how it gets built. When an answer constrains a later decision, name the dependency and follow it before moving on. Prefer multiple choice when natural alternatives exist.

Before wrapping up, run an exhaustiveness check: "Are there branches we haven't covered?" (edge-case users, adjacent features, rollout, success measurement).

Stop when all branches are resolved, or the user says "proceed."

## Write the Spec

Write the full spec in one pass — no section-by-section sign-off. The user reviews the shipped file (see After Saving).

First check whether the spec relies on code only another in-flight ticket's branch adds, per `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md` **Find it**.

## Save

**Resolve the ticket:**
- Input was a **Linear identifier**, or an existing folder with a known ticket → reuse it.
- Input was a **plain idea** → create it now by invoking the `create-ticket` skill (Skill tool), never `save_issue` directly, when contents exist to infer from: title = the spec topic, description = a summary plus the `spec.md` path. Do not set or advance status on any path.

**Write the spec:**
- Save to `workflows/YYYY-MM-DD-<ticket-lowercase>-<slug>/spec.md`, using the ticket identifier (passed or newly created).
- Set the spec's `**Source:**` field to the ticket URL.

**Freeze the design (if referenced):** If the feature has a UI and the run references a paper.design URL, and `paper` is reachable, invoke `workflow-freeze-design` (`../workflow-freeze-design/SKILL.md`) with that URL and `--folder workflows/<folder>`; skip when there's no URL or `paper` is unreachable (e.g. headless). `paper` stays out of this skill's `## Required MCPs` — the sub-step owns it.

**Record the folder on the ticket:** write the `workflows/<folder>/` path to it — a ticket you created here already carries it in its description (the `spec.md` path); on a passed-in ticket, post the path as a comment via `mcp__linear__save_comment` rather than overwriting its description.

**Link dependencies:** link each `## Depends On` entry per `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md` **Link it**.

**Ship it:** hand off per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: spec.md`, `target status: Spec Done`, staging the `design/` bundle alongside `spec.md` when present. **If the ticket has a `parentId`** (an epic sub-issue), pass the parent epic's `gitBranchName` (from `get_issue` on the parent) as **target branch**, so the spec lands on the shared epic branch — where the orchestrator finds it and sibling slice specs sit together — rather than the sub-issue's own branch; the `Spec Done` move still targets the sub-issue.

## spec.md Template

```markdown
# Spec: [Topic]

**Project:** [folder-name]
**Source:** [Linear ticket URL]
**Created:** YYYY-MM-DD

## Problem Statement
[What problem we're solving and why it matters]

## Goals
[What we're trying to achieve - user-facing outcomes]

## Requirements

### Must Have
- [Critical requirements - the feature doesn't work without these]

### Should Have
- [Important but flexible - can adjust approach]

### Won't Have (Out of Scope)
- [Explicitly excluded to prevent scope creep]

## Success Criteria
[How we'll know we're done - from the user's perspective, not technical metrics]

## Constraints
[Timeline, budget, technical limitations, dependencies, etc.]

## Depends On
[Only when the spec relies on code an in-flight ticket adds]

## Open Questions
[Things we need to validate during codebase research]

## Next Steps
- [ ] Research codebase: `/workflow-research [folder-name]`
```

## After Saving

End with the link to the shipped spec — `https://github.com/<owner>/<repo>/blob/<branch>/workflows/<folder>/spec.md`, where `<branch>` is the branch ship-artifact pushed to — alongside its closing summary. No next-step suggestions.

## Rules

- **Interactive mode only:** always use the AskUserQuestion tool for every question, one question at a time — never batch questions. (Headless mode asks nothing — see Execution Mode.)
- **YAGNI ruthlessly** — push back on unnecessary requirements (in headless, just exclude them and note it under `## Assumptions`)
- **Always anchor to a ticket** — read the passed one or create one from the idea; never produce a spec with no Linear ticket behind it.
