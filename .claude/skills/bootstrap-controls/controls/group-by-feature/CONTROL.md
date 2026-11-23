# group-by-feature control

**Holds:** group-by-feature. **Audit module:** `<skills>/audit-principles/principles/group-by-feature/`.

Everything lives in the repo under `controls/group-by-feature/`:

| File | Source |
|---|---|
| `config.json` | the approved config the first audit wrote |
| `check.py` | copied unchanged from the audit module's `check.py`; recopy it in the PR that first gives a path its own `may_use`, since older copies reject that shape |
| `baseline.json` | generated: `python3 controls/group-by-feature/check.py --write-baseline` |

## Install

1. Copy `check.py`. Write the baseline.
2. **CI.** Add a step to the workflow that runs on pull requests. The baseline is compared with the base branch's copy, so the step fetches it first:

   ```yaml
   - name: Group by feature
     run: |
       if [ -n "${{ github.base_ref }}" ]; then
         git fetch --no-tags --depth=1 origin "${{ github.base_ref }}"
         python3 controls/group-by-feature/check.py --base "origin/${{ github.base_ref }}"
       else
         python3 controls/group-by-feature/check.py
       fi
   ```

   Put it in a job whose runner or container has `python3`; GitHub's Ubuntu and macOS runners do, slim language images may not.
3. **Local command.** Chain the check into the repo's lint entry point, so agents hit it before pushing: a `lint:features` script run from `npm run lint`, or a line in the Makefile's `lint` target.
4. **Existing enforcement.** If the audit agreed to replace another boundary check, remove its config and CI step in this PR. If it agreed to run both, leave it.

## Verify

The check passes on the install branch. Then add an empty source file under a root but outside every feature, kernel and shell folder: the check must fail on `placement`. Delete the file.

## Slices

One slice per refactor target in the audit report, plus a close-out slice blocked by the others. Each slice's PR carries the control-file changes its refactor implies:

- `baseline.json` re-recorded with `check.py --write-baseline`.
- In `config.json`: a planned feature the slice creates gets its `paths` and leaves `planned_features`; a `kind-files` entry whose file the slice removes comes off the list; a `may_use` edge the slice removes comes off the list that holds it, the feature's or a path's.

A refactor slice is done when the `known` entries and ratchet numbers it covers are gone from `baseline.json`.

## Close-out

The close-out slice, once every other slice has merged:

- A rule in `baseline` mode with no `known` entries left becomes `strict` in `config.json`.
- Any planned feature, `kind-files` entry or `may_use` edge a refactor slice left stale is fixed per Slices.
- A ratchet at zero stays on; zero is enforced like any other number.
- `audit-principles group-by-feature` re-audits under the new config; its counts must match `baseline.json`. Anything still baselined is named in the PR and filed as a follow-up ticket.

## Why not a setting

| Rule | Closest setting | What it misses |
|---|---|---|
| `placement` | none | Which folder a file belongs in comes from the feature map, which no lint rule reads. |
| `kernel-uses-feature`, `unlisted-edge`, `deep-import`, `uses-shell` | `no-restricted-imports` (not in `templates/eslint`) | Each edge would be its own pattern, regenerated whenever the feature map changes, and TS only: Swift files in one module don't import each other, so the check builds Swift edges from type ownership. |
| `two-cycle` | madge cycles (debt-ratchet template) | Counts file cycles across the whole repo, not two features that depend on each other. |
| `shared-single-user` ratchet | none | Nothing tracks kernel code only one feature uses. |
| `kind-files` ratchet | `max-lines` 500 (ESLint template) | Caps a file's size, not how many features' code it mixes. |
| `cross-feature-duplication` ratchet | jscpd (debt-ratchet template) | Counts duplication across the whole repo, not code copied between two features. |
