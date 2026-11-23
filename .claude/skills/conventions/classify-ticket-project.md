# Convention: Classify Ticket Project

When a factory skill **creates a new Linear ticket**, best-guess which Linear **project** the work belongs to and pass it as `project` on the `mcp__linear__save_issue` create call. Bias toward picking: a wrong guess is cheap to reassign, and leaving new tickets project-less is worse. A passed-in ticket keeps its existing project; never reclassify one.

## Procedure

1. `list_projects team=<team>` for the resolved team.
2. **Caller passed a `project`?** Match it against that list by name, case-insensitively, ignoring surrounding whitespace. A single hit is the chosen project, by its listed name; skip step 3. A value copied from a repo's `Project:` scope field is a filter, not a name: a comma-separated list narrows the candidates to its matches, and a `!name` entry excludes that project — never strip the `!` and file into it. Nothing resolves → drop the override (an unmatched string hard-fails `save_issue`), log it under `## Assumptions`, and classify among the remaining candidates.
3. Classify the ticket's work against the team's rubric (below) — the MECE axis is *what does this work serve?* Pick the single best-fitting project. No rubric → use each project's own Linear summary as its one-line definition.
4. Pass the chosen `project` on create; in headless mode also log it under `## Assumptions`. Only when nothing plausibly fits, leave `project` unset rather than force a clearly-wrong one — an interactive skill may instead ask which project. Route factory-harness work (a `systems-engineer`-labelled or tooling ticket) to the `Factory` project when the team has one.

## Team rubric

The app repo owns its team's rubric: a `## Linear project rubric` section in the repo's `CLAUDE.md` (or `AGENTS.md`), with one guiding question and one bullet per project, each named exactly as in Linear:

```markdown
## Linear project rubric

*What does this ticket's work serve — the core runtime (Engine), the client (Web), or the factory itself (Factory)?*

- **Engine** — the request runtime: sessions, tool loop, tracing.
- **Web** — the browser client: its screens, routing, build.
- **Factory** — the software-factory harness itself.
```

A bullet whose name matches no listed project is ignored; a project with no bullet is classified by its Linear summary.
