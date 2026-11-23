# software-factory

The dev harness every app is built with: the skills, agents and hooks that run the
spec → contract → implement → QA pipeline, plus the quality controls app repos install.

## How it works

This repo is where the factory is written. App repos don't copy it in. They turn it on as the
Claude Code plugin `software-factory@software-factory`, and Claude Code installs a copy of the
plugin for each machine or cloud session.

**Shipping a change.** Everything under `.claude/` ships: the skills, the agents and the hooks.
`plugin/skills`, `plugin/agents` and `plugin/hooks` are symlinks into it. A change reaches app
repos once it merges to main here and the version in `plugin/.claude-plugin/plugin.json` goes up.
App repos only fetch a new copy when that version changes, so a change merged without a bump never
reaches them.

**What runs in an app repo.** Skills and agents work there the same way they do here. Hooks are
different: only the ones listed in `plugin/hooks/hooks.json` run in an app repo. The other two,
`guard-protected-paths.py` and `require-version-bump.py`, are registered only in this repo's
`.claude/settings.json`, so they run only when you work here.

One of the shipped hooks, `inject-conventions.py`, puts every `conventions/*.md` file a loaded skill
references into context, so skills don't depend on the model choosing to read them.
`scripts/convention-coverage.py` measures how often that happens.

**Quality controls.** A control is a check, such as "every file belongs to a feature", that runs in
an app repo's CI. The `bootstrap-controls` skill copies the check into the app repo as ordinary
files and wires it into CI, so it keeps working without the plugin.

## Rules

- Never edit `.claude/skills/**` or `.claude/agents/**` directly. Use the `meta-*` skills; a hook
  blocks direct edits.
- A PR that changes `.claude/skills`, `.claude/agents` or `.claude/hooks` bumps the version in
  `plugin/.claude-plugin/plugin.json`; CI enforces it. `docs/` and this file don't ship.
- Factory tickets go to the Linear team of the app repo you run from and carry the
  `systems-engineer` label. Never add a `Linear team:` line here: it collides with the app repo's
  in a cloud sibling checkout.

## Docs

- [`README.md`](README.md): what the factory is and how app repos consume it
- [`docs/setup.md`](docs/setup.md): turning the factory on in an app repo
- [`docs/pipeline.md`](docs/pipeline.md): moving tickets from spec to review
- [`docs/architecture.md`](docs/architecture.md): how skills, agents and hooks load
- [`docs/principles.md`](docs/principles.md): the principles and what enforces each one
- [`docs/controls.md`](docs/controls.md): the controls an app repo can install
- [`docs/mcp-credentials.md`](docs/mcp-credentials.md): MCP tokens, local and cloud
