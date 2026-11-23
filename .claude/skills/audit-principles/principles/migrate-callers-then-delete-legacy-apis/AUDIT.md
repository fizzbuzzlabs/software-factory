# migrate-callers-then-delete-legacy-apis

**Rule:** when a new internal API replaces an old one, migrate every caller and delete the old API in the same wave, with no compatibility layer left behind.

**Terms.** A *compatibility layer* is an old name or path kept working beside its replacement. A *caller* is a file that imports or names it, production, test or eval. A *site* is one module keeping one or more layers. A *facade* is a module whose re-exports were never definitions, such as an `index` barrel or a store module that has always fronted its types file; its re-exports never count. A *wave* is the PR or epic that introduced the replacement.

**Scripts** (this module's folder, stdlib Python 3.9+, run with `python3 -I`):

- `audit.py propose` drafts a config (production roots, caller-only roots, excludes, TypeScript path aliases), then reads history for each re-export with callers. A symbol once defined in the re-exporting file was moved and stays a violation; one never defined there is proposed as a facade. So is an alias whose name was never defined before the commit that made it an alias: it was born one, not renamed. It prints each candidate with its callers and the commit that decided it.
- `audit.py history` lists mainline commits whose subject suggests a replacement API.
- `check.py --report` prints every violation with its callers, the unused layers (no callers: dead code, not counted), the sites and sites per 10k production lines.
- `test_check.py` tests both scripts: `python3 -I -m unittest discover -s <module> -p 'test_*.py'`. Run it after changing either.

`check.py` rules:

- `reexport-shim`: a module re-exports a repo symbol (`export { X } from`, `export *`, or an import re-exported with `export { X }`) and at least one caller imports it through that module. Re-exports of a library and `index.*` files never count.
- `alias-rename`: `export type Old = New`, `export const Old = New`, `export { New as Old }` or a top-level Swift `typealias Old = New`, where `New` is declared in the repo, with at least one caller. An instantiation such as `Card = Intent<Data>` is a type of its own.
- `deprecated`: a JSDoc `@deprecated`, or Swift `@available` with `deprecated`, `renamed:` or `obsoleted:`. Counts with or without callers.
- `dual-mount`: one router or route factory mounted at two or more prefixes in one file, through the config's `mount_methods` (default `route`). TypeScript only.

Ratchet: `callers`, each baselined violation's caller count. It may only go down, so nothing new attaches to a layer the baseline tolerates.

Not checked: callers in another repo (an app still calling a renamed server route), a function kept only to forward to its replacement, an old generic kept beside a typed one, decoders that accept old and new keys, and class members other than through `@deprecated`. The judgment sample covers these.

## Measure

1. **Draft or load the config.** First audit: `audit.py propose --root . --out <scratch>/config.json`. Re-audit: use `controls/migrate-callers-then-delete-legacy-apis/config.json`.
2. **Count.** `check.py --report --config <config>`.
3. **History.** `audit.py history`. Open 10–12 commits that introduce a replacement API and classify each: *same wave* (old deleted in that PR or epic), *later* (lag in days) or *never* (still on the default branch).
4. **Judgment sample.** Open every site and every proposed facade. Confirm each `moved:` commit really moved the definition, and each facade fronts its module by design. Note the unused layers for subtract-before-you-add; they don't count here.
5. **Existing enforcement.** Find what already fails CI on a compatibility layer: `no-restricted-imports` on old paths, `@typescript-eslint/no-deprecated`, Swift deprecation warnings as errors. Trace the CI step that runs it; a command name in a workflow file is not proof. A test asserting that an alias exists pins the layer: name it.

## Agree (first audit)

Present these in order. After every change, rerun `check.py --report` on the edited config and show the new counts.

1. **Scope.** Roots, caller roots, excludes (generated code) and aliases. A caller outside every root hides a violation.
2. **Facades.** Each proposed facade, and each moved re-export the user calls a facade. Prefer `{"path": ..., "symbols": [...]}` over a whole file, so a new shim in the same module still fails.
3. **Mounts.** Whether `mount_methods` adds `use` (Express); it then also catches middleware mounted at several prefixes.
4. **Strictness.** One row per rule with its count. Recommend `strict` at zero and `baseline` above zero, so only new violations fail. `off` only when the user doesn't want the rule yet. The `callers` ratchet stays on.
5. **Existing enforcement** from Measure step 5: keep it, replace it, or run both. A test pinning an alias goes in the slice that deletes the alias, not in the install.

**New codebase** (no history worth reading, or a few dozen source files): skip the history half of `propose`. Every rule `strict`.

Write the approved config to `controls/migrate-callers-then-delete-legacy-apis/config.json`.

## Rubric

- **5**: ≤ 1 site per 10k production lines, and ≥ 90% of sampled replacements same wave.
- **4**: a handful of sites, ≥ 65% same wave.
- **3**: sites in core paths, about 50% same wave.
- **2**: the shim is the default for one recurring kind of change, seen in ≥ 3 waves or ≥ 5 modules.
- **1**: shims everywhere.

Doesn't count: facades since birth, layers with no callers (dead code: subtract-before-you-add), legacy data rows the reader ignores, rollout flags and architecture-level dual paths (outcome-oriented-execution), database expand/contract migrations.

## Refactor targets

One per unfinished wave: group the sites by the `moved:` or `added:` commit that left them. Each target points every caller at the replacement, deletes the layers and drops any test that pins them; size it in caller files and sites. A layer with callers in another repo is one target across both repos, the other repo's callers switched first.
