---
name: workflow-freeze-design
description: "Freeze a paper.design file/node into a checked-in design bundle under workflows/<folder>/design/ — tokens.css, a reference screenshot, structure.jsx, and a spec.md carrying the fidelity-scope rule + provenance — so cloud pipeline stages can verify frontend fidelity against committed artifacts instead of the local-only Paper MCP. Local-only and re-runnable; invoked by workflow-questions or run standalone. NOT a design conversation (that's workflow-design) and does not ship or advance a ticket."
argument-hint: "<paper.design URL | file-id> [--nodes <id,…>] --folder workflows/<folder>"
---

# Freeze a Paper design into a checked-in bundle

Extract a paper.design node into `workflows/<folder>/design/` so downstream pipeline stages — which run in the cloud and cannot reach the local-only Paper MCP (`127.0.0.1`) — verify frontend fidelity against committed files instead of a live link. Run it locally against a Paper URL, or let `workflow-questions` invoke it when a spec references a design.

## Required MCPs

- paper

See `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md` for the preflight pattern.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`

## Steps

### 0. Preflight

Resolve `paper` per `mcp-preflight-check.md`; missing → halt. The caller — not this skill — decides whether to invoke when Paper may be absent (e.g. headless); if `workflow-freeze-design` runs, Paper must be present.

### 1. Resolve inputs

`open_file` the URL or file-id (it accepts a full URL, a `/file/<id>` path, or a bare id). Pin the target node(s): those named in `--nodes`, else the node id in the URL, else `get_selection`. Never freeze the whole file — it holds unrelated explorations and future features that are out of scope for any one run. Resolve `--folder` to the `workflows/<folder>/` project; write into its `design/` subdirectory.

### 2. Extract exact values

Pull exact values from the MCP, never from screenshots (which verify, not source):

- `get_tokens({format:"css"})` → the design system as CSS custom properties.
- `get_jsx({nodeId})` per pinned node → exact structure.
- `export({nodes:{<id>:[{format:"png",scale:"2x"}]}})` per pinned node → a reference image; move the returned `filePath` into `design/` as `<layer-name-kebab>.png`.
- Note `contentHash.tokens` from any response — the staleness signal.

### 3. Write the bundle

Into `workflows/<folder>/design/`: `tokens.css` (one, file-level), `<screen>.png` and `structure.jsx` per node, and `spec.md` per the template. Emit the two fixed clauses in `spec.md` **verbatim** every run.

### 4. Report

Print the bundle path, pinned node id(s), and `contentHash.tokens` for the invoking skill (or human) to ship on the ticket branch.

## spec.md template

````markdown
# Frozen design spec — [node layer name]

| field | value |
|---|---|
| Paper file | `[name]` — `[file-id]` |
| Page | `[page name]` (`[page-id]`) |
| Node(s) | `[layer name]` (`[node-id]`) |
| Source URL | [url] |
| Artboard | [W] × [H] |
| `contentHash.tokens` | `[hash]` |
| Captured | [YYYY-MM-DD] |

Re-run `workflow-freeze-design` when `open_file` reports a different `contentHash.tokens`, or the node id changes.

## Layout intent

[Prose from get_jsx: structure, the tokens each region uses, key states.]

## Fidelity scope (fixed policy)

This bundle is a fidelity reference, not a feature list. The Paper file may contain
future or exploratory features outside this run.

- IN SCOPE — the app must match this design for (a) functionality that already exists
  in the app and is depicted by the frozen node, and (b) functionality articulated in
  this run's contract.md.
- OUT OF SCOPE — design elements depicting functionality that neither exists nor is
  articulated in this contract MUST NOT be implemented from the design alone. They are
  reference-only.
- DIRECTION — the design governs how in-scope functionality looks; it never mandates
  that new functionality exists. A missing design element is a defect only when it
  belongs to an in-scope behavior.

## Verification tiers

- TIER 1 — Strict (tokens): the app's CSS custom properties must value-match `tokens.css`,
  with no raw literal where a token exists. Machine-checkable; needs no Paper access.
- TIER 2 — Visual (screenshot): per-in-scope-behavior diff against `<screen>.png`,
  tolerance-based. Deferred — not yet enforced.
- TIER 3 — Advisory (structure): `structure.jsx` is a build reference, never asserted.
````

## Rules

- Local-only; never runs in cloud.
- Writes files only — no commit, push, PR, or ticket move.
