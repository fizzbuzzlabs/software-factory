---
name: meta-create-skill
description: Scaffold a new dev-time skill (.claude/skills/<name>/SKILL.md) for working on the software factory repo, then verify it's well-formed and its description triggers cleanly. Use for "create a skill for X", "skillify this workflow", "/meta-create-skill". These are dev-time workflow skills (like workflow-*/meta-*) — NOT runtime skills/<name>/SKILL.md product capabilities the harness loads (for those, edit skills/ directly). For edits to an existing skill, use meta-update-skill.
argument-hint: "[skill-name] [one-line description]"
---

# Meta — Create Skill

Scaffold a new dev-time skill under `.claude/skills/` end-to-end and prove it's well-formed and reachable by its `description`.

## Conventions this skill follows

- `.claude/skills/conventions/file-writing.md`
- `.claude/skills/conventions/factory-location.md`

## Factory target

This skill authors into the **factory**, not the current repo. Before any write, resolve and validate `<factory>` per `.claude/skills/conventions/factory-location.md`; every `.claude/...` path below is under `<factory>/`, and the conflict check scans the factory catalog.

## Steps

### 1. Parse and validate

- `<skill-name>` is kebab-case and matches the directory name. Prefix it with its family when it has one: `workflow-` (a pipeline stage), `meta-` (authoring the factory), `factory-` (a pipeline dispatcher), `verifier-` (evidence capture for one surface; `verify` finds these by prefix). A standalone skill takes a plain verb-noun name (`create-ticket`, `bootstrap-controls`). A new family needs at least two skills that share it — name it and say why.
- Reject a name that collides with an existing `.claude/skills/<name>/` directory.

### 2. Conflict check

Read the frontmatter `description` of every `.claude/skills/*/SKILL.md`. Flag any of:

- **MECE overlap** — an existing skill already covers ≥70% of the scope → route to `meta-update-skill`.
- **Description collision** — the proposed `description` overlaps a sibling's closely enough that the harness can't route between them.

Produce a conflict report.

### 3. Show the plan

```
Skill: <name>
Description: <one-line trigger>
Args: <argument-hint>
File: .claude/skills/<name>/SKILL.md
Conflict check: <findings or none>

Proceed? (yes / revise / cancel)
```

### 4. Scaffold the file

Draft from `${CLAUDE_SKILL_DIR}/template.md`, loaded with the Read tool. Keep its skill-dir tokens exactly as written — they're literal in the file and expand to the new skill's directory when that skill loads. Apply `.claude/skills/conventions/file-writing.md` to the draft. A `workflow-*` skill that runs headless follows `.claude/skills/conventions/execution-mode.md`; a skill that calls MCP tools follows `.claude/skills/conventions/mcp-preflight-check.md`.

### 5. Verify

Re-read the new file: frontmatter parses, `name` equals the directory name, and the `description` reads as a trigger ("Use when…") sharp enough that the harness won't confuse it with a sibling. Read `.claude/skills/conventions/*.md` and check the draft against them: flag any rule it contradicts and any anti-pattern from `file-writing.md` it introduces. Run `scripts/lint-convention-paths.sh` in `<factory>`; it names any convention reference that lacks the skill-directory prefix. Fix before reporting done.

### 6. Confirm

```
Created: <name>/SKILL.md
Conflict check: <resolved findings or none>
```

### 7. Publish

Publish per `.claude/skills/conventions/factory-location.md`.

## Rules

- One skill, one job. If two unrelated triggers fit, that's two skills.
- Creates dev-time `.claude/skills/` skills only. Runtime product capabilities live in `skills/<name>/SKILL.md` — edit those directly.
