# Convention: Factory Location

The `meta-*` authoring skills write into the **factory** repo — the single source
of truth for skills and agents — not the repo you're currently working in. Resolve
`<factory-repo>`, then the working tree `<factory>` to write into, before any write.

## 1. Resolve `<factory-repo>`

The canonical clone. In order, first hit wins:

1. `$CLAUDE_FACTORY_REPO` — set in `~/.claude/settings.json` locally, or in the
   routine environment in the cloud.
2. `~/.config/claude-factory/path` — a file holding the path.
3. Ask the user for the path, and offer to save it to `~/.config/claude-factory/path`.

Confirm it exists, is a git repo, and contains `<factory-repo>/.claude/skills/`. If
any check fails, stop and report — never fall back to the current repo's `.claude/`.

## 2. Resolve `<factory>`

The working tree to write into. Every worktree of the factory sits at a different
path but shares one git directory, so compare git directories, not paths:

```bash
git rev-parse --path-format=absolute --git-common-dir
```

- Resolves to `<factory-repo>/.git` → you're already in the factory. `<factory>` is
  the current working tree root (`git rev-parse --show-toplevel`), whichever branch
  it's on, main checkout included.
- Anything else, or cwd is not a git repo → you're in another repo. Cut a worktree
  off `main` and use it, where `<slug>` names the edit:

```bash
git -C <factory-repo> worktree add <factory-repo>/.claude/worktrees/meta-<slug> -b claude/meta-<slug> main
```

Report `<factory>`, its branch, and its clean/dirty state before writing, so the
user knows which working tree they're editing.

## 3. Write and scan against `<factory>`

- Author into `<factory>/.claude/skills/<name>/` or `<factory>/.claude/agents/<name>.md`.
- Run every collision / overlapping-description scan against the factory catalog
  under `<factory>` (`<factory>/.claude/skills/*`, `<factory>/.claude/agents/*`),
  not the current project.

## 4. Publish

App repos run the factory from their plugin cache, a copy. An edit reaches them only after its
branch merges to `main` with a bumped `version` in `plugin/.claude-plugin/plugin.json` and their
cache updates. A factory checkout loads its own `.claude/` as project files, but a session loads
skills at startup, so no edit affects the session that made it.

Close by publishing: run `git status` in `<factory>` and offer to commit. In a cloud session,
push the branch and open a PR through the GitHub MCP, as in `ship-artifact.md`.
