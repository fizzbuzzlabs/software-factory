---
name: meta-update-plugin
description: Refresh the installed software-factory plugin to its latest shipped version in the current environment, so consuming repos stop running stale cached hooks and skills. Use for "refresh the factory plugin", "update the software-factory plugin", "my plugin cache is stale", "/meta-update-plugin". Updates the installed cache only — does NOT edit plugin source (that's meta-update-skill / meta-update-agent).
argument-hint: ""
---

# Meta — Update Plugin

Consuming repos run a **cached** copy of the software-factory plugin under `~/.claude/plugins/`, not its source, so a fix shipped to source keeps recurring as a bug downstream until the cache is refreshed. This skill refreshes the marketplace clone and re-installs the plugin at every scope it's installed in this environment.

## Steps

### 1. Refresh the marketplace clone

```bash
claude plugin marketplace update software-factory
```

Pulls the local marketplace clone (`~/.claude/plugins/marketplaces/software-factory`) so it learns of newly shipped versions.

### 2. Update every install scope

The plugin can be installed under several scopes and projects at once. Read `~/.claude/plugins/installed_plugins.json`; for each entry under `software-factory@software-factory`, take its `scope` and — project scope only — its `projectPath`. Record each `version` first (step 3 compares). For each entry:

```bash
# project scope: MUST run from projectPath, or it fails "not installed at scope"
cd <projectPath> && claude plugin update software-factory@software-factory --scope project
# any other scope (user / local / managed):
claude plugin update software-factory@software-factory --scope <scope>
```

Update **all** entries — a single un-refreshed scope keeps misbehaving.

### 3. Verify the bump

For each updated entry, confirm its `version` in `installed_plugins.json` advanced to the marketplace's shipped version (`~/.claude/plugins/marketplaces/software-factory/plugin/.claude-plugin/plugin.json`) and its new `installPath` cache dir exists. Report any scope whose version didn't move — that install didn't take.

### 4. Report the restart requirement

Updates apply only after a Claude Code restart — tell the user to restart every session that has the plugin loaded.

## Rules

- Bootstrap caveat: this skill can only run from a plugin version that already ships it. If the environment predates it, run steps 1–2 by hand once; the skill is available afterward.
