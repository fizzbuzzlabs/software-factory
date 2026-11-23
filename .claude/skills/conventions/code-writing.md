# Convention: Code Writing

How a pipeline stage writes app code and tests. Prose in code drifts from the code, and the next agent trusts it and copies the pattern — so code carries no prose, and names carry no ticket numbers.

## No comments

Write no comments in code or tests: no line, block, doc, or header comments. Put what a comment would carry where it can't drift:

- **Why a constraint exists** → a test that fails when the constraint breaks (see *Why-tests*), or a name that states it (`MAX_TURNS_BEFORE_SUMMARY`, `refreshTokenBeforeRetry`).
- **What changed, and for which ticket** → the commit message.
- **Contract traceability** → the contract's `## Behaviors` checklist and the commit message.
- **QA traceability** → the QA commit message (case id → test title) and each finding in the QA ticket comment (`test file › title`).

Two exceptions:

- A generated-code marker (`// @generated`, `// Code generated … DO NOT EDIT.`), emitted by the generator.
- `// eslint-disable-next-line <rule> -- <reason>`: one rule, the next line only, with a reason.

A skip or expected-fail marker states its reason through the framework — the marker's reason argument or the test title — never a comment above it.

Comments and numbered titles in neighbouring files aren't an idiom to match. When you change code an existing comment describes, delete the comment rather than rewrite it; leave the file's other comments for the repo's sweep.

## Test names

Name each test and `describe` block after the behavior it checks, in plain words: `rejects a reminder scheduled in the past`. Never put a ticket key (`ABC-123`), a contract behavior number (`behavior 4`, `B2`), a QA case id (`QA B1-4`, `[QA-B5-1]`), an ambiguity id (`AMB-1`), or an artifact name (`test-plan`, `contract.md`) in a test title, a `describe`, a skip or expected-fail marker's title or reason, or a test file name — they mean nothing once the next contract ships.

Where the repo has a no-comments control, it flags an id in any of those places (`history-id` from `controls/no-comments/check.py`, or the repo's own lint rule). Remove the id; never baseline it, allow it or disable the rule.

## What tests assert

Assert structure — status code, error class or `reason` enum, rendered element, mounted route or provider. Never write these kinds of test:

1. **Prose, CSS text or log wording.** No assertions on UI copy, error/refusal/stderr wording, log lines, doc/skill/prompt prose, or comment text. Where the intent is real, assert presence or absence without the text: an accessible name exists, an error carries *a* reason, a secret is absent from logs. Prompt behavior belongs in evals.
   - Not prose: enum values, IDs, routes, JSON keys, wire field names, env var names, HTTP status, structured `reason` codes.
   - Wording other code waits on is a contract and may be asserted — e.g. the server startup line a readiness check watches for. Lint-rule tests check `messageId`, never `message`.
   - Styling: the one allowed CSS check is that a value resolves to one of the repo's design tokens, with no raw literal where a token exists. On iOS, that a view uses one of the design system's color or type roles — no exact point sizes, padding or corner radii. Accessibility thresholds (contrast floors, Dynamic Type, Bold Text) stay: the number is the requirement.
   - Bad: `expect(res.body.error).toContain('reminder is in the past')`. Good: `expect(res.status).toBe(422)` and `expect(res.body.reason).toBe('past_date')`.
2. **A retired feature staying absent.** When you remove a feature, name, file, dependency or column, delete its tests; add no guard that it stays gone. Typecheck, lint and the next real test catch a regression.
   - Bad: `expect(existsSync('src/legacy-router.ts')).toBe(false)`.
3. **Pins on tuning constants.** No `TIMEOUT_MS > 0`, no `toBe(30000)`, no hand-copied second table of design values. Test the behavior the constant drives, or nothing.
   - Bad: `expect(RETRY_DELAY_MS).toBeGreaterThan(0)`. Good: under fake timers, a failed call is not retried until the delay elapses, then is retried once.
4. **Expected values derived from the code under test.** Write a literal, a hand-built fixture, or a value from the spec — never call the same production function, import the production constant or table, or re-implement the algorithm to compute it. Round-trip property tests are fine. A free-text constant may be referenced by name — `expect(reason).toBe(TERMINAL_REFUSAL_REASON)` — so the test checks which value was chosen without spelling its wording.
   - Bad: `expect(toCents(price)).toBe(Math.round(price * 100))`. Good: `expect(toCents(19.99)).toBe(1999)`.
5. **A re-run of a CI step.** Never spawn `npm run typecheck`, eslint over the tree, a client build, or a nested test run from inside a test — CI and the pre-PR gate already run them. Call the functions directly; keep at most a few end-to-end runs of a script.
   - Bad: `execSync('npx eslint .')` asserting exit code 0. Good: `expect(lintConfig(fixture).errors).toEqual([])`.

Before committing tests, grep their diff for string-literal `toContain` / `toMatch` / `toBe` calls and `> 0` comparisons on SCREAMING_CASE constants. Each hit is a prompt to look, not a ban.

## Why-tests

A **why-test** pins a constraint: an invariant, an ordering, a tie-break, a guard. It proves it guards the constraint only by going red on that constraint — going red because the function didn't exist yet proves nothing. So mutation-check every why-test that hasn't gone red on its own constraint:

1. Break the protected code with an `Edit` (in a worktree, on the worktree copy): delete the guard, flip the condition, or drop the call. Never mutate through the shell (`sed -i`, a codemod's `--find`/`--replace`, `eval`, `node -e`); the worktree guard rejects it (`worktree-isolation.md`).
2. Run the test by its literal path through the repo's test script. Confirm it fails, and for that reason.
3. Restore the code with the reverse `Edit`; `git diff <file>` must come back empty. Never commit the mutation.

Record the check in the commit message (`mutation-checked: dropping the past-date guard fails "rejects a reminder scheduled in the past"`), never in the file. A test that stays green under the mutation guards nothing — fix the test.
