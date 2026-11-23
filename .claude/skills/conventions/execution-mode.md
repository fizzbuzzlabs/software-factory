# Convention: Execution Mode

Every `workflow-*` skill runs **interactively** by default and **headless** when no human is available to answer questions. This convention owns mode detection and the universal headless rules; each skill documents only the behaviors unique to it under a **Headless specifics for this skill** note.

## Detect mode at the start

- If the argument contains `--headless` or `--interactive`, that explicit override wins.
- Otherwise auto-detect: run `test "$CLAUDE_CODE_ENABLE_ASK_USER_QUESTION_TOOL" = true`. Exit 0 → interactive; otherwise headless (e.g. under `claude -p`).
- Strip any `--headless`/`--interactive` token from the argument before parsing the rest per the skill's `argument-hint`.

## When headless

- Never call `AskUserQuestion` — it is unavailable and will error. Make the best-judgment decision instead, using the skill's input artifacts, `CLAUDE.md`, git history, and codebase conventions as the source of truth.
- Record every decision that would have been a question under an `## Assumptions` (or `## Notes`) section of the skill's output artifact: what you assumed and why. List anything you genuinely cannot resolve under `## Open Questions` rather than blocking.
- Launch sub-agents in the foreground (`run_in_background: false`), parallel ones as calls in one message. A headless run has no next turn to collect a background result: ending your turn ends the run (an `Agent` worker's turn end is its hand-back).
- Skip all interactive gates — section-by-section review and save/revise prompts. Run straight through and end with a plain-text summary of the artifact and the key assumptions.
