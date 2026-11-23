# migrate-callers-then-delete-legacy-apis control

**Holds:** migrate-callers-then-delete-legacy-apis. **Audit module:** `<skills>/audit-principles/principles/migrate-callers-then-delete-legacy-apis/`.

Everything lives in the repo under `controls/migrate-callers-then-delete-legacy-apis/`:

| File | Source |
|---|---|
| `config.json` | the approved config the first audit wrote |
| `check.py` | copied unchanged from the audit module's `check.py` |
| `baseline.json` | generated: `python3 controls/migrate-callers-then-delete-legacy-apis/check.py --write-baseline` |

## Install

1. Copy `check.py`. Write the baseline.
2. **CI.** Add a step to the workflow that runs on pull requests. The baseline is compared with the base branch's copy, so the step fetches it first:

   ```yaml
   - name: Migrate callers, then delete legacy APIs
     run: |
       if [ -n "${{ github.base_ref }}" ]; then
         git fetch --no-tags --depth=1 origin "${{ github.base_ref }}"
         python3 controls/migrate-callers-then-delete-legacy-apis/check.py --base "origin/${{ github.base_ref }}"
       else
         python3 controls/migrate-callers-then-delete-legacy-apis/check.py
       fi
   ```

   Put it in a job whose runner or container has `python3`; GitHub's Ubuntu and macOS runners do, slim language images may not.
3. **Local command.** Chain the check into the repo's lint entry point, so agents hit it before pushing: a `lint:legacy-apis` script run from `npm run lint`, or a line in the Makefile's `lint` target.
4. **Existing enforcement.** If the audit agreed to replace another check, remove its config and CI step in this PR. If it agreed to run both, leave it.

## Verify

The check passes on the install branch. Then, in a production root, add three files: `probe-a` exporting `probe`, `probe-b` re-exporting it from `probe-a`, and `probe-c` importing it from `probe-b`. The check must fail on `reexport-shim` for `probe-b`. Delete the files.

## Slices

One slice per refactor target in the audit report, plus a close-out slice blocked by the others. Each slice points every caller at the replacement, deletes the layers and drops any test that pins them. Its PR carries the control-file changes that implies:

- `baseline.json` re-recorded with `check.py --write-baseline`.
- In `config.json`: a facade entry naming a deleted symbol loses it, and an entry left with no symbols comes off.

A refactor slice is done when the `known` entries and `callers` numbers it covers are gone from `baseline.json`.

## Close-out

The close-out slice, once every other slice has merged:

- A rule in `baseline` mode with no `known` entries left becomes `strict` in `config.json`.
- Any facade entry a refactor slice left stale is fixed per Slices.
- The `callers` ratchet stays on; with nothing baselined it holds an empty map.
- `audit-principles migrate-callers-then-delete-legacy-apis` re-audits under the new config; its counts must match `baseline.json`. Anything still baselined is named in the PR and filed as a follow-up ticket.

## Why not a setting

| Rule | Closest setting | What it misses |
|---|---|---|
| `reexport-shim` | none | Telling a re-export kept for old callers from a public entry point needs a model of which files are public, which no lint rule has. |
| `alias-rename` | none | No rule flags `export { New as Old }` or `typealias Old = New`. |
| `deprecated` | `no-deprecated` (in `strictTypeChecked`); `SWIFT_TREAT_WARNINGS_AS_ERRORS` (Swift settings) | Both flag call sites, third-party and platform APIs included, not the deprecated declaration left in this repo. Where `no-comments` is installed the TS half fires only on baselined comments, since `no-comments` bans the `@deprecated` JSDoc it reads. |
| `dual-mount` | none | Where a router is mounted is framework code no lint rule models. |
| `callers` ratchet | none | Nothing counts new callers of a baselined compatibility layer. |
