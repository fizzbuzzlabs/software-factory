---
name: meta-update-skill
description: Edit an existing dev-time skill under .claude/skills/ when it's out of date — runs a conflict check against the conventions and sibling skills before applying. Use for "update the X skill", "the X skill is missing Y", "/meta-update-skill". For a brand-new skill use meta-create-skill; to cut bloat without changing behavior use meta-tighten.
argument-hint: "[skill-name] [what's missing or wrong]"
---

# Meta — Update Skill

Edit a `.claude/skills/<name>/SKILL.md` when it's out of date.

## Invocation modes

- `/meta-update-skill <skill-name> <what's missing>` — direct user invocation.
- Programmatic — another skill passes `{ skill_name, observation, proposed_edit }`.

## Conventions this skill follows

- `.claude/skills/conventions/file-writing.md`
- `.claude/skills/conventions/factory-location.md`

## Factory target

This skill edits skills in the **factory**, not the current repo. Before loading or writing, resolve and validate `<factory>` per `.claude/skills/conventions/factory-location.md`; every `.claude/...` path below is under `<factory>/`.

### 1. Load the target skill

Read `.claude/skills/<skill_name>/SKILL.md`. If missing, stop and ask — new skills go to `meta-create-skill`.

### 2. Load conflict-check context

Read in parallel: every convention the target skill references, `.claude/skills/conventions/file-writing.md`, and the `description` of any sibling `.claude/skills/*/SKILL.md` whose scope overlaps the edit.

### 3. Run the conflict check

Flag any of:

- **Direct contradiction** — the edit tells Claude to do X, but a convention or sibling skill says don't-X.
- **Scope creep** — the edit pulls responsibility away from the skill that owns it.
- **Convention violation** — body structure or authoring rules change without updating the relevant `.claude/skills/conventions/*.md`.
- **Authoring anti-pattern** — the edit introduces any pattern from `.claude/skills/conventions/file-writing.md`.
- **Description drift** — the edit changes how the skill is triggered without updating the `description` frontmatter.

Produce a conflict report.

### 4. Show the plan

```
Skill: <skill_name>
Change: <one-line observation>

Proposed edit:
<unified diff or before/after snippet>

Conflict check:
- <finding, or none>

Apply? (yes / revise / cancel)
```

Programmatic call, zero conflicts, pure addition → apply without asking but still print the summary. Any conflicts → always ask.

### 5. Apply the edit

Run the new text through `.claude/skills/conventions/file-writing.md`. If the surrounding section now duplicates the addition, tighten it in the same diff. Preserve heading levels unless explicitly changing them. Then run `scripts/lint-convention-paths.sh` in `<factory>`; it names any convention reference that lacks the skill-directory prefix, which you fix before confirming.

### 6. Confirm

```
Updated: <skill_name>/SKILL.md
Sections touched: <list>
Sibling edits flagged: <list or none>
```

### 7. Publish

Publish per `.claude/skills/conventions/factory-location.md`.

## Rules

- Don't modify frontmatter without explicit confirmation.
- One-off observations don't warrant an edit. Document only what recurs.
- Run the conflict check on every edit unless the user explicitly says to skip it; then say in the summary that it was skipped.
- One SKILL.md per invocation. Flag sibling edits; don't auto-apply them.
- Don't edit `.claude/skills/conventions/*.md` from here unless the skill edit requires it — convention tightening goes to `meta-tighten`; flag convention edits as separate items.
