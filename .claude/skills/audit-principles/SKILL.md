---
name: audit-principles
description: "Audit how well the current repo follows one engineering principle and score it 1–5, using that principle's module under principles/ (scripts, what counts as a violation, rubric). A first audit is interactive: it drafts the principle's config (for group-by-feature, the feature map), recounts violations as the user edits it, agrees each rule's strictness, and writes the approved config. A re-audit, headless or interactive, measures against the repo's committed config. Use for '/audit-principles group-by-feature', 'audit this repo for group-by-feature', 'how well does this codebase group by feature'; bootstrap-controls invokes it. Does NOT install checks, write baselines, or file tickets (bootstrap-controls)."
argument-hint: "<principle> [--headless | --interactive]"
---

# Audit Principles

Measure one principle in the current repo, judge what the numbers mean, and score it. Each supported principle is a module folder, `${CLAUDE_SKILL_DIR}/principles/<principle>/`. Its `AUDIT.md` owns the principle's terms, scripts, measure steps, what to agree with the user, rubric and refactor targets; read it in full before measuring. Below, `<module>` means that folder.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`

## Steps

### 1. Resolve the principle

Detect the mode per `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`. The argument names a folder under `${CLAUDE_SKILL_DIR}/principles/`. Missing or unknown: list the folders and ask which; headless, stop and print the list.

### 2. Pick the audit

- **Re-audit** when the repo has `controls/<principle>/config.json`. Measure under it as committed. Never edit the config or the baseline: changing what counts as a violation is a first-audit decision or a reviewed PR.
- **First audit** otherwise. It decides what counts as a violation, which is the user's call, so it runs interactive only. Headless, stop: "A first audit agrees the config with the user. Run `/audit-principles <principle>` interactively."

### 3. Measure

Run `<module>/AUDIT.md`'s Measure steps. Scripts live in `<module>`; run them with `python3 -I` from the repo root. Write drafts to the session scratchpad, never into the repo. Open every file the judgment sample names before giving a verdict: the scripts count, you judge.

### 4. Agree (first audit only)

Walk the user through AUDIT.md's Agree section until they approve, then write the approved config where it says. Leave it uncommitted.

### 5. Report

Score against AUDIT.md's rubric and emit:

```
## <principle> audit: <repo> @ <short sha>, <YYYY-MM-DD>
Score: <1–5>. <one sentence against the rubric>
Audit: first | re-audit

| Rule or ratchet | Mode | Count |
|---|---|---|

Scatter: median <m>, p90 <p>, n=<units of work>
Judgment sample: <legitimate vs scatter, with the files that decided it>
Existing enforcement: <what fails CI today, traced>

Refactor targets (largest first):
1. <target>: <files / lines>, clears <rule or ratchet entries>
```

Return the report to the caller. Run standalone, print it. Write no report file into the repo.

## Rules

- A new principle is a new module folder: `AUDIT.md` with Measure, Agree, Rubric and Refactor targets sections, plus any scripts it names.
