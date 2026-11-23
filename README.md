# <img src="docs/assets/logo.svg" alt="" width="36" align="top"> FizzBuzz Software Factory

A software factory for non-technical or lightly technical solo builders who want to ship at
frontier lab velocity.

## The factory in action

<img src="docs/assets/factory.gif" alt="Tickets moving across the board from To do to Ready for review, with an agent working each stage in parallel">

## What this is

A Claude Code plugin that lets one person run a software team of agents. You write specs, then
review the finished tickets together, in the app, from one pooled PR. The factory manages
everything in between, including:

- sequencing work
- resolving conflicts
- stacking finished tickets
- verification + QA
- refactoring the codebase
- (coming soon) auto-queueing bug fixes

## How it works

```
01  you write the specs
├── /workflow-questions ABC-12   → spec.md
├── /workflow-quick ABC-13       → contract.md
├── /workflow-questions ABC-14   → spec.md
└── …

02  the factory runs the pipeline
└── /factory-pipeline
    ├── architect + cto   → contract.md
    ├── orchestrator      → dependency check
    ├── dev               → code + verify
    ├── qa                → adversarial QA
    │   ├── a bug         → back to dev
    │   └── a gap         → back to architect
    └── orchestrator      → review pool

03  you review the PR
└── review-pool → main
    ├── walk through the new features
    └── → merge
```

Tickets run in parallel, each moving the moment its checks pass. The orchestrator holds back any
ticket with unfinished blockers or overlapping files. At the end, you review one PR. Bigger features
can go in an epic: its slices build on a shared branch and land together as their own PR.

The [pipeline guide](docs/pipeline.md) has the full flow, including epics and what
happens when a ticket gets stuck.

## What you need

| | | |
| --- | --- | --- |
| **Claude Code** | Required | The desktop app, the CLI or cloud sessions |
| **Linear** + its MCP server | Required | Tickets, statuses and labels drive the whole pipeline |
| **GitHub** + its MCP server | Required | Every PR the pipeline opens goes through the GitHub MCP |
| `git`, `gh`, `node` / `npm`, `python3` | Required | `python3` runs the plugin's hooks; `node` runs the browser checks |
| A `verify` skill in your app repo | Required | How `dev` checks a change in your running app -- the factory can't know how your app runs |
| CI that runs on pull requests | Required | Checks the pool + epic PRs; `/bootstrap-controls` won't install a control without it |
| [Paper](https://paper.design) | Optional | Only for freezing a design into the repo (`/workflow-freeze-design`) |

## Setup

Open Claude Code in your app repo and paste this:

```
Read the setup guide at
https://github.com/fizzbuzzlabs/software-factory/blob/main/docs/setup.md
and set up the software factory plugin in this repo.
Walk me through any step you can't do yourself.
```

The [setup guide](docs/setup.md) has every step in full if you'd rather do it by hand.

## Controls

The factory also includes controls that force agents to follow engineering best practices in your
codebase, e.g. "every file belongs to a feature" or "no swallowed errors". Each control is a check
that runs in your app repo's CI, so it has to be bootstrapped into each app repo. The checks cover
TypeScript/JavaScript, Swift and CSS; in another language, none applies yet.

After you've installed the plugin, open Claude Code in your app repo and paste this:

```
Read the controls catalog at
https://github.com/fizzbuzzlabs/software-factory/blob/main/docs/controls.md
and help me pick the controls that fit this repo.
Install each one I choose, one at a time, with /bootstrap-controls or its template.
```

The [controls catalog](docs/controls.md) has every control and how to install it.

## Plugin components

Skills and agents are namespaced (`software-factory:workflow-contract`), so they never clash with
your repo's own.

- **Stage skills** (`workflow-*`): spec, research, design, contract, contract review, implement,
  QA plan + test, and amending an artifact after feedback.
- **Dispatchers** (`factory-*`): the whole pipeline, one stage's queue, the review pool and epic
  branches.
- **Agents**: `architect`, `cto`, `dev`, `qa` and `systems-engineer`, plus read-only
  `codebase-*` and `web-search-researcher` helpers for research.
- **Everyday skills**: `create-ticket`, `report-bug` (investigate a bug in the running app and file
  it with a root cause) and `verifier-web` (browser evidence for `verify`).
- **Authoring skills** (`meta-*`): create, update and tighten the factory's own skills and agents.
- **Hooks**: guards that stop an agent from printing a secret or chaining a destructive git cleanup.

## Resources

- [Setup guide](docs/setup.md)
- [Pipeline guide](docs/pipeline.md)
- [Controls catalog](docs/controls.md)
- [Engineering principles](docs/principles.md)
- [Architecture](docs/architecture.md)
- [Security policy](SECURITY.md): report security problems privately

## Credits

- The pipeline builds on HumanLayer's
  [research → plan → implement](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents)
  workflow, and several agents are adapted from [theirs](https://github.com/humanlayer/skills)
  (MIT, see [NOTICE](NOTICE)).
- Many [principles](docs/principles.md) come from Lauren Tan's
  [pstack](https://github.com/cursor/plugins/tree/main/pstack) (MIT, see [NOTICE](NOTICE)).

These credits acknowledge work this project builds on. They don't imply that its authors are
affiliated with the project or endorse it.

## License

MIT -- see [LICENSE](LICENSE) and [NOTICE](NOTICE).
