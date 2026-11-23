# group-by-feature

**Rule:** a feature's code (routes, store, logic, UI, tools) lives in its own folder, so changing one feature doesn't mean touching files scattered across the tree.

**Terms.** A *feature* is one or more folders holding one feature's code; its `may_use` lists the features it may depend on. A `paths` entry is a folder, or `{"path": ..., "may_use": [...]}` when files under that folder have their own list, such as a feature split into a client folder and a server folder; that list replaces the feature's. The *kernel* is shared code no feature owns, and it may not depend on a feature. The *shell* is the composition root (entry points, app wiring): it may depend on anything, and nothing depends on it. A *kind folder* groups code by technical role (`components/`, `services/`) and holds feature code.

**Scripts** (this module's folder, stdlib Python 3.9+, run with `python3 -I`):

- `audit.py propose` drafts a config and prints a summary: roots, features, kernel, shell, kind folders, files named after a feature but sitting outside it, planned features (names recurring across kind folders), large files spanning several features, and the edges observed between features.
- `audit.py scatter` counts the features each unit of work touched in history.
- `check.py --report` prints every violation and ratchet number under a config, and the features each feature path uses (`path_edges`).
- `test_check.py` tests both scripts: `python3 -I -m unittest discover -s <module> -p 'test_*.py'`. Run it after changing either.

`check.py` rules: `placement` (a source file in no feature, kernel or shell), `kernel-uses-feature`, `unlisted-edge` (a feature using one outside its `may_use`), `deep-import` (TypeScript, only for features that list `public` files), `two-cycle`, `uses-shell`. Ratchets: `shared-single-user` (kernel files only one feature uses), `kind-files` (line counts of listed grab-bag files), `cross-feature-duplication` (lines duplicated between features).

## Measure

1. **Draft or load the map.** First audit: `audit.py propose --root . --out <scratch>/config.json`. Re-measure: use `controls/group-by-feature/config.json`.
2. **Count.** `check.py --report --config <config>`.
3. **Scatter.** `audit.py scatter --config <config>`, adding `--ticket '<regex>'` when commit subjects carry ticket ids.
4. **Judgment sample.** Open the files of the 10 highest-scatter units of work. Classify each extra feature touched as legitimate (wire contract, kernel, composition root, cross-cutting sweep) or scatter (the same feature living in a second place). Open every kind folder, every kind file and the top 5 duplication pairs, and confirm each holds feature code.
5. **Existing enforcement.** Find what already fails CI on a boundary violation: dependency-cruiser, eslint-plugin-boundaries, a feature lint script, separate Swift targets. Trace the CI step that runs it; a command name in a workflow file is not proof.

## Agree (first audit)

Present these in order. After every change, rerun `check.py --report` on the edited config and show the new counts.

1. **The map.** Features with their paths, kernel, shell, planned features with their proposed moves, and unplaced files. Settle the map before strictness.
2. **The edges.** Observed edges become `may_use`; where a feature's paths use different features, `propose` drafts a `may_use` per path. Point out mutual edges and edges that moving code to the kernel would remove. An edge the user prunes becomes an `unlisted-edge` violation.
3. **Strictness.** One row per rule with its count. Recommend `strict` at zero and `baseline` above zero, so only new violations fail. `off` only when the user doesn't want the rule yet. Ratchets start on at today's numbers; confirm the `kind-files` list.
4. **Existing enforcement** from Measure step 5: keep it, replace it, or run both. Never install a second boundary check silently.

**New codebase** (no feature folders yet, or a few dozen source files): skip `propose`. Agree the first features, the kernel and the shell; folders may not exist yet. Every rule `strict`, every ratchet on.

Write the approved config to `controls/group-by-feature/config.json`. Keep `planned_features` for names that have no folder yet.

## Rubric

- **5**: feature folders throughout, scatter median 1 and p90 ≤ 2, boundaries enforced in CI.
- **4**: feature-grouped core with ≤ 2 confirmed scatter sites, scatter median ≤ 2.
- **3**: feature grouping is the norm, but a core feature or a kind folder splits code routinely; median 2–3.
- **2**: whole layers organized by kind, or multi-feature hubs that most features must edit; p90 ≥ 8.
- **1**: no feature grouping.

Doesn't count as scatter: a client / server / wire-contract split, a single composition root that registers each feature in one line, a shared kernel (design system, logging), a cross-cutting sweep.

## Refactor targets

One per extraction, sized in files and lines: create a planned feature from its proposed moves, split a kind file into the features' own files, merge a duplication pair into the feature that owns the logic, move a single-user kernel module into its feature, remove a pruned edge.
