# Type-aware ESLint and tsconfig: per-repo install

One ESLint config and one tsconfig fragment: the ESLint + tsconfig row of the
[controls catalog](../../docs/controls.md). The base is
typescript-eslint `strictTypeChecked` with `projectService: true`, plus `@eslint/js`
`recommended`. On top of that, `eslint.config.ts` groups its rules into one object per principle,
named after the principle, so you can see which principle a rule holds without a comment. (App
repos ban comments.)

This directory is a **template**, not a shipped package. It is not symlinked into the installed
factory plugin cache. You copy from a factory checkout, referenced as
`$CLAUDE_FACTORY_REPO/templates/eslint` (see step 6 of the
[setup guide](../../docs/setup.md)). **Once copied, the files belong to the
app repo.** Edit them there. Later changes to this template don't reach the copy. To pick them up,
diff the copy against the template by hand.

## Files here

- `eslint.config.ts`: the flat config. Three constants carry this repo's layout and must be checked
  (step 3): `loggerFiles`, `testFiles` and the `ignores` entry.
- `tsconfig.principles.json`: the five tsconfig controls. Every tsconfig project `extends` it.
- `package.json.scripts`: the `lint` and `typecheck` lines to paste into `package.json`.
- `ci-step.yml`: the typecheck and lint CI steps, plus the suppressions ratchet for an existing repo.

## What each rule holds

| Principle | Rules |
|---|---|
| boundary-discipline | `consistent-type-assertions` (`assertionStyle: "never"`), the five `no-unsafe-*` rules, and a `no-restricted-syntax` selector that bans a type argument on `.json<T>()` (Hono's `c.req.json<T>()`, for example), which asserts a body's type without a cast |
| type-system-discipline | `no-explicit-any`, `no-non-null-assertion`, `ban-ts-comment`, plus `consistent-type-assertions` and the tsconfig settings |
| model-the-domain | `switch-exhaustiveness-check` (a `default` doesn't count as covering a union's missing cases) |
| never-swallow-a-failure | `no-floating-promises` (`ignoreVoid: false`), `no-misused-promises`, `return-await`, `only-throw-error`, `prefer-promise-reject-errors`, `use-unknown-in-catch-callback-variable`, `no-empty` (`allowEmptyCatch: false`), and a `no-restricted-syntax` selector that bans a `.catch()` callback that does nothing (`() => {}`, `() => undefined`, `() => null`, `() => void 0`) |
| fix-root-causes | `no-unnecessary-condition` |
| one-logger | `no-restricted-globals` on `console`, which flags every use of the global, called or passed as a value (`wire(console)`), and a `no-restricted-syntax` selector that bans `process.stdout.write` and `process.stderr.write`. Both are off in `loggerFiles` |
| minimize-reader-load | `max-lines` 500, `max-lines-per-function` 100, `no-restricted-imports` on `node:async_hooks` |
| subtract-before-you-add | `no-unused-vars`, `no-unused-private-class-members`, `reportUnusedDisableDirectives: "error"` |
| test-behavior-not-implementation | vitest `expect-expect` and `valid-expect`, and a `no-restricted-syntax` selector that bans `vi.mock`/`vi.doMock` of the repo's own modules (paths starting `./`, `../`, `@/` or `~/`). These apply to `testFiles` only |

In `testFiles`, type assertions, non-null assertions and the two length caps are off. The principles
count those only in production code. The rest of `strictTypeChecked` stays on as typescript-eslint
ships it.

Left out on purpose: `complexity`, `max-depth` and `max-params`. No principle's spec counts
branching, nesting or arity, so they'd be style. Also left out: `consistent-type-definitions`
(style), `no-empty-function` (too broad; the `.catch()` selector covers the case that matters), and
a ban on top-level `let` (minimize-reader-load excludes lazy caches, which use one).

## Install

1. **Install the tools** as devDependencies:

   ```bash
   npm i -D eslint @eslint/js typescript-eslint @vitest/eslint-plugin typescript
   ```

   Node 22.18 or later loads `eslint.config.ts` natively. On an older Node, also install `jiti`.

2. **Copy the files in.** Copy `eslint.config.ts` and `tsconfig.principles.json` to the repo root.
   Remove any other ESLint config, or merge its rules into `eslint.config.ts`.

3. **Point the config at this repo's layout.** In `eslint.config.ts`:
   - `loggerFiles`: the logger module, the only files allowed to use `console` or write to
     `process.stdout` and `process.stderr`. A repo with no logger yet names the path it will have,
     and every sink fails (or is suppressed) until a ticket adds the logger there. A CLI whose
     output is the product belongs here too.
   - `testFiles`: globs that match every test file.
   - `ignores`: build output and generated code.

4. **Extend the tsconfig fragment.** In every tsconfig project, add `"./tsconfig.principles.json"`
   to `extends` (it takes an array) and delete any of the five settings the project sets itself.
   Every file ESLint lints must belong to some tsconfig's `include`, `eslint.config.ts` too.
   Otherwise the project service reports "was not found by the project service".

5. **Add the scripts.** Paste the lines from `package.json.scripts`. Make `typecheck` cover every
   tsconfig project.

6. **Turn it on**, by one of the two paths below.

7. **Add the CI steps.** Paste `ci-step.yml` into the pull-request job, after `npm ci`. CI must
   typecheck every tsconfig project and run `eslint` with `--max-warnings 0`. Leave out the
   suppressions step on a new repo.

### New repo: everything is an error from day one

Run `npm run typecheck && npm run lint`, fix what they report, and commit. There's no baseline.

### Existing repo: baseline today's violations, then burn them down

ESLint first:

```bash
npx eslint . --fix --fix-type directive   # deletes eslint-disable directives that suppress nothing
npx eslint . --suppress-all               # writes eslint-suppressions.json
npm run lint                              # passes
```

The first command is needed because an unused-directive error has no rule id, so `--suppress-all`
can't record it. Read the summary before you commit. Commit `eslint-suppressions.json`. It records
a count per file per rule.

From then on, the file can only shrink:

- A new violation fails lint. So does an extra violation in a file that already has suppressions
  for that rule.
- Fixing a suppressed violation also fails lint, until `npx eslint . --prune-suppressions` removes
  its entry. So every fix shrinks the file in the same PR.
- The `ESLint suppressions only shrink` CI step fails a PR when any rule's total count rises
  against the base branch. That's the one way left to grow the file: rerunning `--suppress-all`.
  Totals are per rule, so moving a file with suppressions still passes.

Then file tickets to burn the file down, one per rule or per directory. Each ticket fixes the
violations and runs `--prune-suppressions`. Skip what a Module control's refactor epic burns down:
`never-swallow-a-failure` takes `no-floating-promises`, `no-misused-promises`, `no-empty` and the
`.catch()` findings of `no-restricted-syntax`.

tsconfig has no baseline. Turn on each of the five settings that already typechecks clean. For
each one that doesn't, delete its line from `tsconfig.principles.json` and file a ticket that fixes
the errors and puts the line back.

## Notes

- **Type-aware linting is slow.** Every typed rule needs a TypeScript program, so `npm run lint`
  costs about as much as a full typecheck, and more on a large repo. Locally, lint the files you
  changed (`npx eslint <files>`). Don't use `--cache` in CI: the cache is keyed on file content, and
  a change to a type in another file can change a typed rule's result.
- **Disabling a rule on one line.** Use `// eslint-disable-next-line <rule> -- <reason>`, the one
  comment form the `no-comments` control allows.
