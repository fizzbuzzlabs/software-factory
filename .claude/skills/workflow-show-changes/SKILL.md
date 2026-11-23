---
name: workflow-show-changes
description: "Sync docs/architecture.html to the working tree and attach a highlighted delta image to the ticket — invoked by workflow-implement at PR-open (sibling to the verify gate), and sync-only (`--tree`) over an assembled pool or epic branch. A bundled script re-derives the FILES map and import-graph edges deterministically and rewrites ONLY those data literals; the agent adds/refreshes nodes (sum/eli5) and edge kinds for new modules; then it renders the touched nodes marked and attaches that image to the Linear issue (no PR comment). No-op when the file is absent or in orchestrator mode. Does NOT touch the explorer's layout/CSS/interaction shell, and does NOT decide a verdict (that's verify)."
argument-hint: "[ABC-123] [--tree <path>] [--headless]"
---

# Show changes — sync + highlight the architecture explorer

`docs/architecture.html` (in the app repo) is a hand-authored interactive explorer whose data lives in five JS literals — `N` (nodes), `ELI5`, `FILES`, `E` (edges), `LAYERS` — plus an optional `SHOW_CHANGES` config literal (see Config). This skill keeps those honest: it re-derives the file lists and import-graph edges, commits the updated file onto the branch, and attaches a diagram image with this PR's touched nodes highlighted to the ticket.

## Required MCPs

None. The ticket attach rides on `highlight.mjs` + `LINEAR_API_TOKEN` (the same raw token `verifier-web` uses), not the Linear MCP — an attach failure logs a note and never fails the run.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`

## Config (optional)

`derive.mjs` reads an optional `SHOW_CHANGES` literal from the target HTML:

- `roots` — directories to enumerate (e.g. `['apps','packages']` or `['src','client']`); `[]`/absent scans the whole tree.
- `ignore` — path prefixes dropped from enumeration entirely (e.g. a shared package every node imports, kept as a footnote instead of a node); absent → drop nothing.
- `aggregateFrom` — node ids whose outgoing edges are `aggregate`; absent → no `aggregate` edges.
- `readTarget` — regex; an import whose resolved target matches it is a `read` edge (default `-(store|repo)\.ts$`).

## Modes

Pick one before step 1:

- **Orchestrator mode** (your brief carries run-stage's **Orchestrator mode** line) → no-op: report "architecture sync deferred to the assembled branch" and return — per-ticket syncs conflict across stacked tickets, and the attach is a Linear write that mode forbids.
- **Assembled branch** (`--tree <path>`, no ticket) → steps 1–4 with `<path>` as `<app-repo-root>`, skipping step 5: no single ticket to attach to. The default `--base origin/main` spans every ticket on the branch. `<path>` is another worktree, so the isolation guard refuses `Edit`/`Write` on it, and a `cd` doesn't change that: never attempt them. Make step 3's edits with `patch-literals.mjs`. Commit with `git -C <path>` onto the branch checked out there; the caller pushes.
- **Ticket** (a ticket id) → every step, in the app repo's working tree.

## Steps

### 1. Locate the file, or no-op

Resolve `docs/architecture.html` in the app repo's working tree. Absent → report "no architecture explorer; skipped" and return — a clean skip, not a failure.

### 2. Derive (deterministic)

Run and read the JSON report:

```bash
node ${CLAUDE_SKILL_DIR}/derive.mjs --repo <app-repo-root> --html <app-repo-root>/docs/architecture.html
```

`diff.unmapped` lists working-tree source files matching no node glob; `diff.filesChanged`, `diff.editedNodes`, `diff.edgesAdded`, `diff.edgesRemoved` are the mechanical delta. `diff.editedNodes` is nodes whose already-mapped files were edited in this branch's diff against `--base` (default `origin/main`; degrades to `[]` when that ref is unavailable) and that aren't already structural.

### 3. Sync the judgment parts (`N` / `ELI5` / `LAYERS`, and `http`/`persist` edges in `E`)

Resolve every `unmapped` file — **never leave one dropped**:

- A file belonging to an existing node → widen that node's `glob` in `N` so `derive.mjs` claims it.
- A new module/domain with no home → add a node: an id, `label` and `glob` in `N`, its id into a `LAYERS` group, a `sum` (technical) in `N` and an `eli5` (plain-language) in `ELI5`.

Refresh the `sum`/`eli5` of any node whose responsibility materially changed.

**Assembled branch:** `Read` the text to change, `Write` the edits to a JSON file in your scratchpad (never under `<path>`), and apply them all in one run. Each `old` must match exactly once inside its `literal`, and a failed edit writes nothing:

```bash
node ${CLAUDE_SKILL_DIR}/patch-literals.mjs --html <path>/docs/architecture.html --edits <edits.json>
```

```json
[{ "literal": "N", "old": "<exact text>", "new": "<replacement>" }]
```

`literal` is `N`, `ELI5` or `LAYERS`, or `E` for a new `http`/`persist` edge (step 4). No such edit to make → skip the script.

### 4. Rewrite `FILES` + `E` and commit

```bash
node ${CLAUDE_SKILL_DIR}/derive.mjs --repo <app-repo-root> --html <app-repo-root>/docs/architecture.html --write
```

This surgically replaces only the `FILES` and `E` blocks (import-derived `flow`/`read`/`aggregate` edges; cross-boundary `http`/`persist` edges are carried over since they never appear in the import graph — add or reclassify those by hand in step 3's pass if a new one is real). When the file changed, commit `docs/architecture.html` onto the current branch with a message naming it a diagram sync.

### 5. Highlight the delta and attach to the ticket

Two node tiers, structural priority. The **structural** set (`--changed`) is nodes added ∪ `diff.filesChanged` — drawn solid amber + glow. The **edited** set (`--edited`) is `diff.editedNodes` minus that structural set — drawn dashed amber, no glow, one color. An edge's endpoints are **not** highlighted. Pass `diff.edgesChanged` as `--edges` and `diff.edgesDeleted` as `--removed`; the diagram draws only those two edge sets, not the whole graph:

```bash
node ${CLAUDE_SKILL_DIR}/highlight.mjs --html <app-repo-root>/docs/architecture.html \
  --out <abs-out-dir> --changed <id,id,...> --edited <id,id,...> --edges <from|to|kind,...> --removed <from|to|kind,...> --ticket <ABC-123> \
  --summary "New node: X; 3 nodes edited; new edge Recipe→Pipeline; deleted edge Foo→Bar"
```

Produce and attach the image when the structural set, the edited set, **or** either edge set is non-empty — a content-only PR yields an image of dashed edited nodes. All four empty → no image; say so. **Never post a PR comment** — the delta lives on the ticket.

`highlight.mjs` reuses the Playwright vendored in `../verifier-web`; if that install is missing, provision it per `${CLAUDE_SKILL_DIR}/../verifier-web/SKILL.md` first. When it can't be provisioned, `highlight.mjs` exits 0 with a skip note and attaches no image — a clean SKIP, not a run failure.

## Rules

- Edit only the `N`/`ELI5`/`FILES`/`E`/`LAYERS` literals. The surrounding shell is hand-crafted and must never be regenerated.
- `FILES` and the import-derived `E` edges (`flow`/`read`/`aggregate`) change only through `derive.mjs --write`; a hand edit reintroduces diff noise. `http`/`persist` edges aren't derived, so step 3 edits them by hand and `--write` carries them over.
- The app repo's `docs/architecture.html` is product code — this skill edits it during a run but adds no product-repo features (e.g. a `?changed=` URL param); surface those to the app team.
