# Convention: File Writing

How to write or edit an authored system file — a `SKILL.md`, a `.claude/skills/conventions/*.md` file, or a subagent definition (`.claude/agents/<name>.md`) — without introducing rot. These are the authoring anti-patterns that make such files go stale silently. Read before scaffolding a new skill or agent, editing a skill, or tightening any of them.

## Calibration: what dense looks like

Trust the model. Every line in a SKILL.md should change behavior the model wouldn't already exhibit by default. If a line just describes standard LLM behavior or restates a heading, cut it.

**Directive budget:** healthy SKILL.md files run under ~40 imperative directives. Past that, ask whether each one is overriding a default or just decorating.

### Exemplars

From Matt Pocock's skills collection (github.com/mattpocock/skills). Study the density — every line changes behavior.

**`grill-me` — 2 sentences, no phases**

```
Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

If a question can be answered by exploring the codebase, explore the codebase instead.
```

Why it works: "relentlessly" sets intensity. "Each branch of the design tree" gives structure without numbered phases. The one constraint (prefer codebase over asking) is the only non-obvious behavior.

**`triage-issue` — minimal questions, bias toward action**

```
Investigate a reported problem, find its root cause, and create a GitHub issue with a TDD fix plan. This is a mostly hands-off workflow - minimize questions to the user.

### 1. Capture the problem
Get a brief description of the issue from the user. If they haven't provided one, ask ONE question: "What's the problem you're seeing?"
Do NOT ask follow-up questions yet. Start investigating immediately.
```

Why it works: "ONE question" and "Do NOT ask follow-up questions" override default model chattiness. The phase structure earns its keep because the model needs to gate (investigate before proposing fixes).

**`write-a-prd` — phases earn their place**

```
1. Ask the user for a long, detailed description of the problem they want to solve and any potential ideas for solutions.
2. Explore the repo to verify their assertions and understand the current state of the codebase.
3. Interview the user relentlessly about every aspect of this plan until you reach a shared understanding.
4. Sketch out the major modules you will need to build or modify to complete the implementation.
5. Once you have a complete understanding, use the template below to write the PRD.
```

Why it works: 5 steps, each one sentence. No sub-bullets explaining how to do each step. "You may skip steps if you don't consider them necessary" trusts the model.

### What earns its place

- Output templates (verbatim structure the model should emit)
- Behavioral overrides (things the model wouldn't do by default — e.g. the headless-vs-interactive split in the `workflow-*` skills)
- Boundary constraints ("do NOT do X" when X is a likely default)
- Philosophy that changes decisions ("deep modules over shallow modules")

### What doesn't

- Describing standard LLM behavior (ask questions, validate, be flexible)
- Listing example questions the model could ask (it knows how to interview)
- Explaining what phases mean after naming them
- Hedged instructions ("consider whether", "you may want to")

## Anti-patterns

**#1–7 apply to any authored file — SKILL.md, convention, or agent definition.** General authoring hygiene: prose rot, delegation, duplication, coherence.

### 1. No tombstone commentary

Describe the current state, not what changed. Lines like *"X is no longer skipped"* or *"used to do Y, now does Z"* belong in PR descriptions and commit messages. Inside a SKILL.md they decay the moment someone forgets the prior state was real.

**Fix:** delete the historical framing. State the rule as it stands.

### 2. Don't restate a delegate's behavior

When skill A delegates to skill B, A should link to B and stop. Restating *"B handles X, Y, Z"* inside A means B's section can change without A's restatement updating — silent drift.

**Fix:** one sentence saying "invoke B (see `path/to/B/SKILL.md`)" with whatever input is being passed. No summary of B's internals.

### 3. One procedure, one home

If two skills need the same procedure (mode detection, a search pattern, a write protocol), one place owns it; the others invoke or reference. Inline duplication = N places to update on every change, with no compiler to catch the misses. The `workflow-*` skills' shared mode-detection procedure lives in `.claude/skills/conventions/execution-mode.md`; each skill links it and keeps only its skill-specific behavior.

**Fix:** identify the natural owner (a convention, or the skill whose primary purpose *is* that procedure), keep it there, replace the duplicate with a one-line delegation.

### 4. Cut vestigial taxonomies

Before adding a classification step (e.g. "auto-detect type from keywords: A / B / C / D / E"), name what downstream branch it gates. If nothing branches on the label, the taxonomy is ceremony — Claude already reads the input and adapts without it.

**Fix:** if the label drives no branching, delete it. If it drives one or two branches, inline the conditional ("if the issue title contains 'research', do X") rather than introducing a named taxonomy.

### 5. Skip / exception lists need re-evaluation when scope expands

When a skill's domain grows, its skip list often needs to *shrink*, not grow exceptions. Patches like *"skip X — except if A, or B, or C"* signal the underlying boundary is wrong.

**Fix:** when editing a skip / exception list, re-read the original rationale. If the rationale no longer holds, drop the rule entirely. Don't tack on exceptions.

### 6. Inline-define skill-specific jargon

If a SKILL.md uses a term that's only defined in another file (e.g. "tracer bullet", "behavior" as a contract unit), readers have to chase the definition. One-skill-only jargon doesn't earn its keep.

**Fix:** inline-define on first use, in plain English. Or just use the plain-English phrase and skip the jargon.

### 7. Audit order-of-operations for "X then re-do X with better input"

If a skill does X, gathers more input, and then does X again with the better input, the right fix is usually to make X accept that better input as a parameter — not to keep two X's. Two passes through the same procedure with different inputs is a smell that the input contract is wrong.

**Fix:** generalize the procedure's input source. Add a single invocation point that takes whatever input the caller has at the moment it's ready.

**#8–10 don't apply to conventions.** #8 governs the `## Conventions this skill follows` list, which only a SKILL.md carries. #9 governs `description`-driven triggering — a SKILL.md or an agent definition has `description` frontmatter; a convention file has none. #10 governs a body's required runtime reads — a convention is read as reference, never executed as a runtime body.

### 8. Convention links speak for themselves

When a SKILL.md links the conventions it follows, list each by path with no trailing gloss. A line like `` - `.claude/skills/conventions/foo.md` — explains the foo rule `` restates what the convention itself should make clear, and goes stale when the convention is rewritten. Same drift mode as #2, applied to convention references instead of skill delegations.

**Fix:** bare bulleted links only, in the #10 path form. If the convention's purpose isn't obvious from its name, fix the convention's own opening line — not the SKILL.md that links to it.

### 9. Don't restate triggers in the body

Triggering is driven by the `description` frontmatter (alongside `argument-hint` and `disable-model-invocation`), which is read *before* the body loads. Natural-language trigger phrases written into the body fire nothing and drift from the real `description`.

**Fix:** delete body-level trigger-phrase restatements. If triggering is weak, sharpen the `description` frontmatter instead.

### 10. A body's required file reads must resolve via the plugin, not just the checkout

An agent or `SKILL.md` body runs in two places: the factory checkout, where `.claude/skills/…` exists, and a repo consuming the factory as a plugin, where it does not — the content ships in the plugin cache under a path the body can't assume. So any required step that raw-`Read`s or `cat`s a repo-relative sibling (`.claude/skills/conventions/execution-mode.md`) hard-fails the moment the body runs in a consumer repo.

**Fix — by body type:**

- **A `SKILL.md`** references every convention — list entry or inline `per …` — as `${CLAUDE_SKILL_DIR}/../conventions/X.md`. The harness replaces the token with the skill's absolute directory before the body reaches the model, so the model sees a real path that resolves in the checkout and the plugin cache alike, from any cwd, with the Read tool or `cat`. A bare `../conventions/X.md` resolves against cwd — a worker's worktree — and fails; the agent then guesses a version-pinned cache path. `scripts/lint-convention-paths.sh` (CI) rejects bare references. The harness expands the token anywhere in a SKILL.md body, code blocks included — text that must show it literally (e.g. `meta-create-skill/template.md`) lives in a sibling file the skill `Read`s.
- **A body with no reliable base-dir anchor** — an agent definition, whose cwd is the consumer repo — can't count on that path resolving. Inline the one-sentence operative rule it must act on, and name the owning convention rather than ordering a runtime `Read`.

The `## Conventions this skill follows` list uses that same form — a bare pointer (#8), not an executed step. Reserve literal `.claude/…` reads and writes for the `meta-*` skills, which resolve `<factory>` first.

## When to apply

- **Creating a skill or agent** — the scaffold should pass every applicable anti-pattern before commit; #8 is SKILL.md-only, #9–10 skip conventions.
- **Editing a skill or agent** — ask "does this edit introduce any anti-pattern from `file-writing.md`?" before committing.
- **Tightening a skill, convention, or agent** (`meta-tighten`) — the calibration examples are the stop signal; the anti-patterns are the cut list. #8–10 apply only where the target carries the structure they name.
- **Reviewing a change to any of these files** — these are the things to look for in a diff.

## Why this exists

SKILL.md files, conventions, and agent definitions rot in characteristic ways: tombstones from refactors, restatements of delegated behavior, duplicated procedures, taxonomies that lost their branches, skip lists patched into incoherence, jargon left undefined, re-do-with-better-input patterns, trigger phrases stranded in the body, and required reads that assume the checkout layout. Naming the patterns makes them visible at authoring time, which is the cheapest place to catch them.
