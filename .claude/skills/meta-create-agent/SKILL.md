---
name: meta-create-agent
description: Scaffold a new Claude Code subagent (.claude/agents/<name>.md) for working on the software factory, then verify it. Use for "create an agent that <does X to the repo>" or /meta-create-agent. These are dev-time subagents launched via the Agent tool — NOT runtime skills/<name>/SKILL.md product capabilities, which the harness loads (for those, edit skills/ directly).
argument-hint: "[agent-name] [one-line role]"
---

# Meta — Create Agent

Scaffold and verify a `.claude/agents/<name>.md` subagent definition.

## Conventions this skill follows

- `.claude/skills/conventions/file-writing.md`
- `.claude/skills/conventions/factory-location.md`

## Factory target

This skill authors into the **factory**, not the current repo. Before any write, resolve and validate `<factory>` per `.claude/skills/conventions/factory-location.md`; every `.claude/...` path below is under `<factory>/`, and the conflict check scans the factory catalog.

## Steps

### 1. Parse and validate

- `<agent-name>` is kebab-case and matches the filename.
- Reject a name that collides with an existing `.claude/agents/<name>.md`.

### 2. Gather config

Resolve four values: the agent's **job** (one paragraph of role + scope), its **trigger** (the `description` — when the parent should delegate to it), its **tool allowlist** (least privilege), and its **model** (`sonnet` default; `opus` for heavy reasoning, `haiku` for cheap mechanical passes). Ask only for what the invocation left unspecified.

### 3. Conflict check

Read every existing `.claude/agents/*.md`. Flag an overlapping `description` — colliding triggers make delegation ambiguous.

### 4. Show the plan

```
Agent: <name>
Job: <one line>
Trigger (description): <when to delegate>
Tools: <allowlist | inherit-all>
Model: <sonnet | opus | haiku>
File: .claude/agents/<name>.md
Conflict check: <findings or none>

Proceed? (yes / revise / cancel)
```

### 5. Scaffold the file

Fill the template below, keeping the system prompt dense per `.claude/skills/conventions/file-writing.md`.

### 6. Verify

Re-read the new file: frontmatter parses, `name` equals the filename, every entry on `tools` is a real tool name, and the `description` reads as a trigger ("Use when…") rather than a label.

### 7. Publish

Publish per `.claude/skills/conventions/factory-location.md`.

## Rules

- Least-privilege tools. A read-only reviewer gets `Read, Grep, Glob` — not `Edit`, `Write`, or `Bash`. A read-only search agent may hold `Bash` (some sessions expose no `Grep`/`Glob`) only if you add it to `GUARDED_AGENTS` in `.claude/hooks/guard-readonly-search.py`, which holds it to search commands.
- The `description` carries delegation; sharpen it there, never with trigger phrases in the body.
- One agent, one job. If the role needs two unrelated triggers, that's two agents.

## Template (`<name>.md`)

````markdown
---
name: <name>
description: Use this agent when <trigger condition on the software factory repo>. <One sentence on what it does.>
tools: Read, Grep, Glob
model: sonnet
---

You are the **<Role>** subagent in the software factory — <one-line scope: which layer of the repo, e.g. the harness/seams, the runtime skills under `skills/`, the eval suite, the client>.

## First

<What to read before acting — e.g. the relevant `src/*.ts`, `docs/VISION_PRD.md`, the `skills/<name>/SKILL.md` under review. Name concrete paths.>

## Job

<The single thing this agent does, and the boundary of it. State what it must NOT do if a default agent would overreach.>

## Hand back

<What the agent returns to the parent — a review, a diff, a written artifact, a recommendation. Be specific so the parent can act without re-deriving.>
````
