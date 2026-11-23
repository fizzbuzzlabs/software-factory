---
name: meta-tighten
description: Critical editing pass on an existing dev-time skill, convention file, or agent definition under .claude/ to cut bloat, remove over-explanation, and tighten prose per conventions/file-writing.md. Use when a skill, convention, or agent feels too long, wordy, or over-engineered — or right after creating/updating one. Does NOT add new behavior (use meta-update-skill for that).
argument-hint: "[skill-name or path]"
---

# Meta — Tighten

Read a SKILL.md, a `.claude/skills/conventions/*.md` file, or an agent definition (`.claude/agents/<name>.md`) and cut it down per `.claude/skills/conventions/file-writing.md` — apply the anti-patterns as cuts, use the calibration exemplars as the stop signal.

## Invocation modes

- `/meta-tighten <skill-name or path>` — direct user invocation.
- Programmatic — chained after `meta-create-skill` / `meta-update-skill` when the result runs long. Payload `{ skill_name }`.

## Conventions this skill follows

- `.claude/skills/conventions/file-writing.md`
- `.claude/skills/conventions/factory-location.md`

## Factory target

This skill tightens files in the **factory**, not the current repo. Before reading or writing, resolve and validate `<factory>` per `.claude/skills/conventions/factory-location.md`; the `.claude/...` paths below are under `<factory>/`.

### 1. Locate and read the target

Resolve `<arg>`: bare name → `.claude/skills/<name>/SKILL.md`; a `.claude/skills/conventions/*.md` or `.claude/agents/<name>.md` path → treat as a path. Read the file.

### 2. Apply the cuts

Load `.claude/skills/conventions/file-writing.md`. Propose cuts, grouped by anti-pattern, each with a before/after diff and a one-line rationale. #8–9 apply only to a SKILL.md target. After cutting, compare against the calibration exemplars — if density still looks padded, keep cutting; if the final directive count exceeds ~40, flag it.

### 3. Show the full edited file

Present the tightened file end-to-end.

### 4. Confirm and write

After approval, write the file. Re-read to verify it's intact; for a SKILL.md or agent definition, confirm the frontmatter still parses (`name` / `description` preserved).

### 5. Publish

Publish per `.claude/skills/conventions/factory-location.md`.

## Rules

- **Never add new behavior.** If a cut would change *what* the target does, stop and route to `meta-update-skill`.
- **Preserve frontmatter (SKILL.md / agent def).** `name`, `description`, and the rest of the frontmatter keys stay intact unless the `description` itself is the bloat. A convention file has no frontmatter.
- **Preserve triggering (SKILL.md).** Don't weaken the `description` or drop documented args — that's what routes the skill.
- **Show diffs before writing.** No silent rewrites.
