---
name: meta-update-agent
description: Edit an existing subagent definition under .claude/agents/ when its description, tools, model, or system prompt are out of date — runs a conflict check against sibling agents before applying. Use for "update the X agent", "the X agent's trigger is too broad", "/meta-update-agent". For a brand-new agent use meta-create-agent.
argument-hint: "[agent-name] [what's wrong]"
---

# Meta — Update Agent

Edit an out-of-date `.claude/agents/<name>.md`, conflict-checking it against its siblings first.

## Invocation modes

- `/meta-update-agent <agent-name> <what's wrong>` — direct user invocation.
- Programmatic — another skill/agent passes `{ agent_name, observation, proposed_edit }`.

## Conventions this skill follows

- `.claude/skills/conventions/file-writing.md`
- `.claude/skills/conventions/factory-location.md`

## Factory target

This skill edits agents in the **factory**, not the current repo. Before loading or writing, resolve and validate `<factory>` per `.claude/skills/conventions/factory-location.md`; every `.claude/...` path below is under `<factory>/`.

## Steps

### 1. Load the target agent

Read `.claude/agents/<agent_name>.md`. If missing, stop and ask — new agents go to `meta-create-agent`.

### 2. Load conflict-check context

Read the `description` frontmatter of every sibling `.claude/agents/*.md`. If the edit changes tools or the system prompt, also read whatever the agent's `## First` names as its inputs, so the edit stays consistent with them.

### 3. Run the conflict check

Flag any of:

- **Trigger collision** — the edited `description` now overlaps a sibling's, making delegation ambiguous. This is the primary failure.
- **Scope creep** — the edit gives the agent a second, unrelated job. A second trigger means a second agent.
- **Tool over-grant** — the edit adds tools the job doesn't need. Least privilege: a read-only agent gets `Read, Grep, Glob`, not `Edit`/`Write`/`Bash`. Exception: a read-only search agent may hold `Bash` (some sessions expose no `Grep`/`Glob`) only when `.claude/hooks/guard-readonly-search.py`'s `GUARDED_AGENTS` lists it, which holds it to search commands.
- **Boundary loss** — the edit removes a "do NOT" the agent needs to stop overreaching (e.g. a builder agent losing its "don't merge the PR" line).
- **Description drift** — the system prompt changes what the agent does without updating the `description` that triggers it.

### 4. Show the plan

```
Agent: <agent_name>
Change: <one-line observation>

Proposed edit:
<unified diff or before/after snippet>

Conflict check:
- <finding, or none>

Apply? (yes / revise / cancel)
```

Programmatic call, zero conflicts, pure addition → apply without asking but still print the summary. Any conflicts → always ask.

### 5. Apply the edit

Run new prose through `.claude/skills/conventions/file-writing.md`. Prefer a targeted `Edit`; a full `Write` rewrite is rare. Preserve frontmatter keys and heading structure unless the edit is explicitly changing them.

### 6. Confirm

```
Updated: <agent_name>.md
Fields touched: <description | tools | model | prompt sections>
Sibling triggers flagged: <list or none>
```

### 7. Publish

Publish per `.claude/skills/conventions/factory-location.md`.

## Rules

- Delegation lives in the `description`; sharpen triggering there, never with trigger phrases in the body.
- Don't change `name` — it must equal the filename.
- The conflict check is mandatory unless the user says "just apply it" — then skip it and say you did.
- One agent def per invocation. Flag sibling edits; don't auto-apply them.
