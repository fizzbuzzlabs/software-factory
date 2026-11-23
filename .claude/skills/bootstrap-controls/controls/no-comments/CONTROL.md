# no-comments control

**Holds:** no-comments. **Audit module:** `<skills>/audit-principles/principles/no-comments/`.

Everything lives in the repo under `controls/no-comments/`:

| File | Source |
|---|---|
| `config.json` | the approved config the first audit wrote |
| `check.py` | copied unchanged from the audit module's `check.py` |
| `baseline.json` | generated: `python3 controls/no-comments/check.py --write-baseline` |

## Install

1. Copy `check.py`. Write the baseline.
2. **CI.** Add a step to the workflow that runs on pull requests. The baseline is compared with the base branch's copy, so the step fetches it first:

   ```yaml
   - name: No comments
     run: |
       if [ -n "${{ github.base_ref }}" ]; then
         git fetch --no-tags --depth=1 origin "${{ github.base_ref }}"
         python3 controls/no-comments/check.py --base "origin/${{ github.base_ref }}"
       else
         python3 controls/no-comments/check.py
       fi
   ```

   Put it in a job whose runner or container has `python3`; GitHub's Ubuntu and macOS runners do, slim language images may not.
3. **Local command.** Chain the check into the repo's lint entry point, so agents hit it before pushing: a `lint:comments` script run from `npm run lint`, or a line in the Makefile's `lint` target.
4. **Existing enforcement.** If the audit agreed to replace an ESLint comment plugin or SwiftLint comment rules, remove them and any bypass guard that only protects them in this PR. If it agreed to run both, leave them.

## Verify

The check passes on the install branch. Then add `// x` to a source file: the check must fail on `comment`. Add a test titled after a ticket id (`it("<key>-1 renders", …)` or `@Test("<key>-1 renders")`) to a test file: it must fail on `history-id`. Revert both.

## Slices

One slice per refactor target in the audit report, plus a close-out slice blocked by the others. A slice that deletes a comment explaining a guard, such as a `catch {}`, carries that why into a log or a test, never a bare guard. Each slice's PR carries the control-file changes its refactor implies:

- `baseline.json` re-recorded with `check.py --write-baseline`.
- In `config.json`: an `allow` pattern the slice retires is removed.

A refactor slice is done when the `known` entries it covers are gone from `baseline.json`.

## Close-out

The close-out slice, once every other slice has merged:

- A rule in `baseline` mode with no `known` entries left becomes `strict` in `config.json`.
- An `allow` pattern that no longer matches any comment is removed (`check.py --report` lists, under `allowed`, only the patterns that matched).
- `audit-principles no-comments` re-audits under the new config; its counts must match `baseline.json`. Anything still baselined is named in the PR and filed as a follow-up ticket.

## Why not a setting

| Rule | Closest setting | What it misses |
|---|---|---|
| `comment` (TS) | `ban-ts-comment` (ESLint template); `no-warning-comments` (not in `templates/eslint`) | They cover only `@ts-` directives and TODO-style terms. No ESLint rule bans comments in general. |
| `comment` (Swift, CSS) | none | SwiftLint has no built-in rule banning comments, and the factory installs no CSS linter. |
| `history-id` | `vitest/valid-title` with `mustNotMatch` (not in `templates/eslint`) | It would cover TS test titles only, not test file names, skip reasons or Swift tests. |
