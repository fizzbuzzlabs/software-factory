# Setup guide

How to turn the factory on in an app repo. Each step says what to add and why; the skills and
docs it links to have the details.

**1. Enable the plugin.** Add this to the repo's `.claude/settings.json` and commit it, so every
clone and cloud session picks it up:

```json
{
  "extraKnownMarketplaces": {
    "software-factory": {
      "source": { "source": "github", "repo": "fizzbuzzlabs/software-factory" }
    }
  },
  "enabledPlugins": { "software-factory@software-factory": true }
}
```

**2. Connect Linear and GitHub.** Both are required: Linear tickets drive the pipeline, and every
PR it opens goes through the GitHub MCP. A skill that needs one stops if it isn't connected.
Commit this `.mcp.json` at the repo root. Keep the names `linear` and `github`: the skills call
`mcp__linear__*` and `mcp__github__*` tools.

```json
{
  "mcpServers": {
    "linear": {
      "type": "http",
      "url": "https://mcp.linear.app/mcp",
      "headers": { "Authorization": "Bearer ${LINEAR_API_TOKEN}" }
    },
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}" }
    }
  }
}
```

The first time you open the repo, Claude Code asks you to approve the repo's servers: approve both.
Then pre-approve the tools and the git commands the dispatchers run, in the repo's
`.claude/settings.json`:

```json
{ "permissions": { "allow": ["mcp__linear", "mcp__github", "Bash(git worktree *)", "Bash(git -C * worktree *)", "Bash(git branch -D *)", "Bash(git -C * branch -D *)", "Bash(git -C * fetch *)"] } }
```

Paper is optional, for `/workflow-freeze-design` only. If you use it, add it once for your user,
not in `.mcp.json`; [`mcp-credentials.md`](mcp-credentials.md#paper-optional) has the command.

**3. Give the MCPs their tokens.** On a Mac, a launchd plist exports each token at login. In a
cloud environment, the Linear key is a network secret and the cloud supplies GitHub.
[`mcp-credentials.md`](mcp-credentials.md) has both setups, including the cloud environment's
fields and setup script.

**4. Set up the Linear team.** The pipeline moves tickets by status. Add Spec Done, Contract
Review, Ready for Dev, Ready for QA and (if missing) In Review as type **Started**, in this order on the board.
Statuses can only be created in Linear's UI (**Settings → Teams → your team → Workflow**):

```
Todo → Spec Done → Contract Review → Ready for Dev → Ready for QA → In Review → Done
```

Then the labels. `create-ticket` creates a missing one, but define the first two before a real
run: they're what stop two runs from taking the same ticket.

| Label | Meaning |
| --- | --- |
| `in progress` | A run holds the ticket. A crashed run leaves it behind; clear it by hand. |
| `needs attention` | A worker stopped for a human. Every queue skips it until you remove the label. |
| `systems-engineer` | On a `Todo` ticket, sends it to the factory's own queue instead of `dev`. |
| `bug` | Filed by `report-bug`. |

Add a `Factory` project for factory and tooling tickets, and a `Linear team:` line to the repo's
`CLAUDE.md`, e.g. `**Linear team:** Acme`. When two separate apps share one team, add a `Project:`
filter so each app's queues claim only its own tickets: `**Linear team:** Acme · **Project:** Web`
(project names to include, or `!name` to exclude). One app split across repos needs no filter; it
runs from one repo (**An app split across repos**, below).

**5. Add what only your repo can supply.**

- **A `verify` skill** (`.claude/skills/verify/SKILL.md`), required: how `dev` and the review
  pool check a change in your running app. The factory calls it with a checkout path, a diff range
  and `--ticket <id>`. It drives the real app, not the tests, and ends with one line:
  `VERDICT: <PASS | FAIL | SKIP | BLOCKED> — <reason>`. SKIP means the diff touches nothing the app
  loads; BLOCKED `port-busy` means its port was taken. For a web app, it records the run with the
  factory's `verifier-web` skill, which needs a launcher that boots the app on a free port and
  passes its URL as `APP_URL`. The
  [sample app's `verify`](../evals/pipeline/sample-app/_claude/skills/verify/SKILL.md) is a worked
  example.
- **CI on pull requests**, required: it checks the pool and epic PRs, and `bootstrap-controls`
  won't install a control without it. The factory opens PRs as drafts and marks them ready for
  review, so CI can skip drafts to save minutes.
- **`.claude/launch.json`** with the app's port, only for a web app that uses `report-bug`.
- **`.claude/hooks/session-start.sh` and `ensure-services.sh`**, only if the pipeline needs a
  service such as Postgres: the first provisions it once per cloud container, the second brings
  it up in each worker's worktree.

**An app split across repos** (a web app and an iOS app, say) runs the whole pipeline from one of
them, the home repo:

- **The home repo** lists the others in a `Sibling repos:` line in its `CLAUDE.md`:
  `<name> (<local path>, <owner>/<repo>[, check: <workflow>])`, where `check` names a home-repo
  workflow that compares the two sides. Every ticket's planning files (`spec.md`, `contract.md`
  and the rest) live in the home repo's `workflows/`, and dev and QA run once in each repo the
  contract touches, on the same branch name.
- **Run `/factory-pipeline` and `/factory-stage` from the home repo only.** A sibling runs no queue
  of its own, so it needs no `Project:` filter. The home session starts each sibling's workers with
  `claude -p`, so the `claude` CLI must be signed in (`claude /login`) on that machine. Signing in
  to the desktop app alone isn't enough.
- **Each sibling** still needs steps 1–3, a `Linear team:` line for the skills you run there
  directly (`create-ticket`, `report-bug`), and its own `verify` skill and CI.

**6. Clone the factory, if you'll copy a control template or edit the factory.** Set
`CLAUDE_FACTORY_REPO` at user level in `~/.claude/settings.json`, or in the cloud environment:

```json
{ "env": { "CLAUDE_FACTORY_REPO": "/absolute/path/to/software-factory" } }
```

**7. Check it loaded.** Plugins load at session start, so open a fresh session. `/plugin` should
show `software-factory@software-factory` enabled, `/workflow-contract` and the
`software-factory:architect` agent should be available, and `claude mcp list` should show
`linear` and `github` connected.

**8. Install controls** (optional). Pick from the [controls catalog](controls.md).

Once the repo is set up, see the [pipeline guide](pipeline.md).
