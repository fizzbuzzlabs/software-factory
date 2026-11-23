# never-swallow-a-failure control

**Holds:** never-swallow-a-failure. **Audit module:** `<skills>/audit-principles/principles/never-swallow-a-failure/`.

Everything lives in the repo under `controls/never-swallow-a-failure/`:

| File | Source |
|---|---|
| `config.json` | the approved config the first audit wrote |
| `check.py` | copied unchanged from the audit module's `check.py` |
| `baseline.json` | generated: `python3 controls/never-swallow-a-failure/check.py --write-baseline` |

## Install

The lint rules in the audit module's AUDIT.md must already run in CI (its Measure step 1 stops without them). This check leaves to them floating promises, empty TS catch blocks and `.catch()` callbacks, and `try!`.

1. Copy `check.py`. Write the baseline.
2. **CI.** Add a step to the workflow that runs on pull requests. The baseline is compared with the base branch's copy, so the step fetches it first:

   ```yaml
   - name: Never swallow a failure
     run: |
       if [ -n "${{ github.base_ref }}" ]; then
         git fetch --no-tags --depth=1 origin "${{ github.base_ref }}"
         python3 controls/never-swallow-a-failure/check.py --base "origin/${{ github.base_ref }}"
       else
         python3 controls/never-swallow-a-failure/check.py
       fi
   ```

   Put it in a job whose runner or container has `python3`; GitHub's Ubuntu and macOS runners do, slim language images may not.
3. **Local command.** Chain the check into the repo's lint entry point, so agents hit it before pushing: a `lint:failures` script run from `npm run lint`, or a line in the Makefile's `lint` target.

## Verify

The check passes on the install branch. Then add `try { JSON.parse("x"); } catch { /* ignored */ }` (TS) or `_ = try? JSONSerialization.jsonObject(with: Data())` (Swift) to a production file: the check must fail on `empty-catch` or `discarded-try`. Revert the line.

## Slices

One slice per refactor target in the audit report, plus a close-out slice blocked by the others. Each slice's PR re-records `baseline.json` with `check.py --write-baseline`. The lint rules' findings in `eslint-suppressions.json` belong to this epic too, not to the ESLint template's burn-down: a slice that fixes them runs `npx eslint . --prune-suppressions`. A refactor slice is done when the `known` entries and suppressions it covers are gone and the swallowed sites the audit's sample named for it log, rethrow or return a typed failure.

## Close-out

The close-out slice, once every other slice has merged:

- A rule in `baseline` mode with no `known` entries left becomes `strict` in `config.json`.
- `audit-principles never-swallow-a-failure` re-audits under the new config; its counts must match `baseline.json`. Anything still baselined is named in the PR and filed as a follow-up ticket.

## Why not a setting

| Rule | Closest setting | What it misses |
|---|---|---|
| `empty-catch` (TS) | `no-empty` (ESLint template) | `no-empty` counts a block holding only a comment as non-empty. |
| `empty-catch` (Swift) | none | SwiftLint has no built-in empty-`catch` rule. |
| `discarded-try` | `SWIFT_TREAT_WARNINGS_AS_ERRORS` (Swift settings) | The unused-result warning fires only on a bare `try? f()` where `f` returns a non-`Void` value and isn't `@discardableResult`. It misses `_ = try?` and `Void` calls. |
| `throwing-task` | none | `Task.init` is `@discardableResult`, so the compiler is silent about a dropped throwing `Task {}`. |
