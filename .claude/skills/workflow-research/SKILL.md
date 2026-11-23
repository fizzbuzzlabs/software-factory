---
name: workflow-research
description: "Research how the codebase handles what a ticket touches, with parallel sub-agents, and write it up as research.md, documenting what exists without critiquing it. Use after spec.md, before workflow-design."
argument-hint: "[ABC-123 | project-folder | research question] [--headless]"
---

# Research

Find out how the codebase does what the ticket touches, and write it down in `research.md`. **Document what exists.** Don't evaluate, critique or suggest improvements, and where the codebase has competing patterns, record each as a fact without picking one: `workflow-design` makes that call.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`

## Research

Resolve the argument to a project folder per `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md` and read its `spec.md` and any existing `research.md`. A plain research question has no folder yet: create `workflows/YYYY-MM-DD-[ticket]-[description]/` when you save (interactive: ask where to save, or whether to).

Always research the code afresh; an existing document is context, not a substitute. Read anything the request names yourself, in full, before delegating.

- **Codebase** — `codebase-locator`, `codebase-analyzer`, `codebase-pattern-finder`. Size the fan-out to the question: a narrow change may need one locator, or none. Use analyzers only on what you can't read yourself in a few tool calls, and tell each agent what to find, not how to search.
- **Web** — for security, payments, cryptography, external API integrations and compliance, or when asked: `web-search-researcher`, told to return source URLs.
- **Context worktrees** in your brief (sibling repos) are researched too, by absolute path, read-only, with findings cited as `<repo>:path:line` so the contract can tag each behavior with its repo.
- **In-flight tickets** — when the folder name carries a ticket id, check whether the ticket relies on code only another ticket's branch adds, per `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md` **Find it**.

Keep at most 3 sub-agents in flight. A spawn refused for the concurrency limit never ran: launch it again after one of yours returns, or do that part yourself. Never write as if a refused agent had reported.

## Write and ship

```markdown
# Research: [Topic]

**Project:** [folder-name]
**Conducted:** YYYY-MM-DD

## Summary
## Detailed Findings
## Code References
## Competing Patterns
[When multiple approaches exist for the same concern, document each:
where it's used, how it differs, and any observable tradeoffs — without recommending one]
## External Sources
[Only if web research was performed]
## Depends On
[Only when the ticket depends on an in-flight ticket]
## Next Steps
- [ ] Create design: `/workflow-design [folder-name]`
```

Cite `file:line` throughout. When the folder name carries a ticket id, link each `## Depends On` entry per `${CLAUDE_SKILL_DIR}/../conventions/depends-on.md` **Link it**, then hand off per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: research.md`, `target status: none`, and end with the link to the shipped file. Otherwise leave `research.md` local.
