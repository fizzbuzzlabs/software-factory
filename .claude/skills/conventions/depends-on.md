# Convention: Depends On

How a spec or research step finds that its ticket relies on code another in-flight ticket adds, and how that becomes a Linear `blocked-by`.

## Find it

The candidates are every other ticket in project scope (`factory-stage` **Resolve IDs**) at Spec Done, Contract Review, Ready for Dev, Ready for QA or In Review whose `origin/<gitBranchName>` carries a `contract.md` in `workflows/*-<ticket-lowercase>-*/`. Read each one's `## Footprint`, `## Behaviors` and `## Modules`.

This ticket **depends on** a candidate when something it relies on (a module, function, endpoint, schema, file) is missing from this ticket's lane base, `origin/main` or, for an epic sub-issue, `origin/<epic gitBranchName>`, and that candidate's contract adds it. Code already on the lane base is never a dependency, whoever wrote it.

Record each under `## Depends On` in your artifact, one bullet per ticket: `- <TICKET-ID> — <what this ticket relies on, naming the file or symbol>`.

## Link it

Under your brief's **Orchestrator mode** line, stop at the record: the architect hands it back as `depends_on` and the dispatcher links it. Otherwise link each entry yourself:

- **Blocker** — the depended-on ticket, or its epic per `factory-pipeline` **Conflicting tickets** (only a sibling slice waits on a slice); the entry then carries the slice: `<relies on> (<SLICE-ID>)`.
- **Nothing to add** — this ticket, or its epic, is already `blocked-by` the blocker.
- **Can't wait** — the blocker is Canceled, or is itself `blocked-by` this ticket, so the wait would never end. Add no relation. A dispatcher still moves the ticket per `stage-verdicts.md`, then halts it there: `needs attention` and the comment below; a skill lists it under the artifact's `## Open Questions` instead.
- **Otherwise** — add the `blocked-by` on this ticket (`mcp__linear__save_issue` with `blockedBy`) and one comment on it per blocker, one bullet per entry.

```
**Blocked by <BLOCKER-ID>** — relies on code only its branch adds:
- <relies on>

**Can't wait on <BLOCKER-ID>** — <it is Canceled | it is blocked by this ticket>; this ticket relies on:
- <relies on>
```

The ticket waits where it is, per `factory-pipeline` **When a ticket is ready**.
