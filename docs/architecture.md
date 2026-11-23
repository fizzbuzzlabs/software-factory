# Architecture

The factory is one repo of Claude Code skills, agents and hooks. App repos don't copy it in: they
run it as a plugin, the same way on a laptop and in a cloud session.

```
software-factory/
├── .claude/
│   ├── skills/     ← workflow-*, factory-*, meta-*, conventions
│   ├── agents/     ← architect, cto, dev, qa, systems-engineer, codebase-*, ...
│   └── hooks/
├── .claude-plugin/marketplace.json   ← declares the software-factory marketplace
├── plugin/         ← plugin.json (manifest + version); skills, agents, hooks symlink to .claude/
└── templates/      ← control templates app repos copy in
```

## Skills, agents and conventions

- **Skills** do the work. The `workflow-*` skills are the pipeline's stages (spec, research,
  design, contract, implement, QA); the `factory-*` skills dispatch them across many tickets.
- **Agents** run one stage headless: `architect`, `cto`, `dev`, `qa`, plus `systems-engineer`
  for the factory's own tickets. Each agent invokes its stage's skills.
- **Conventions** (`.claude/skills/conventions/`) hold the rules several skills share, so each
  rule has one home. The `inject-conventions` hook loads every convention a skill references
  when the skill loads.

## How an app repo gets it

An app repo commits two keys to its `.claude/settings.json` ([setup guide](setup.md), step 1),
and Claude Code installs the plugin from GitHub into a local cache. Skills and agents are
namespaced (`software-factory:workflow-contract`), so they never clash with the repo's own.

The cache is a copy. A change reaches app repos only after it merges to `main` with a higher
`version` in `plugin/.claude-plugin/plugin.json`, the app repo's cache updates (`/plugin`, or
`/meta-update-plugin`), and a new session starts. CI fails a PR that changes `.claude/` without
the bump.

A plugin beats a checked-in copy because it opts in with one committed change, namespaces
everything, ships hooks with no per-repo wiring, and versions the cache.

## Hooks

Hooks listed in `plugin/hooks/hooks.json` run in every app repo: the secret-echo, read-only
search and chained-cleanup guards, and `inject-conventions`. Two run only in
the factory, from its own `.claude/settings.json`: `guard-protected-paths.py`, which blocks direct
edits to skills and agents, and `require-version-bump.py`, which reminds you to bump the
version.

## Changing the factory

Work in a factory checkout, where `.claude/` loads as ordinary project files. Edit skills and
agents through the `meta-*` skills, which find the checkout and the branch to write to
([`factory-location.md`](../.claude/skills/conventions/factory-location.md)). A cloud session
working a factory ticket checks the factory out next to the app repo and edits it the same way.
