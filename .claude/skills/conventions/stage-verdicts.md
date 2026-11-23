# Convention: Stage Verdicts

The Linear status a dispatcher (`factory-pipeline`, `factory-stage`) moves a ticket to for each outcome below. A dispatched worker never moves the ticket; this table is the one home of the mapping.

## Verdict → status

| Returned | Status |
|---|---|
| architect `done`, `route: ready_for_qa` | **Ready for QA**, skipping cto and dev |
| architect `done`, otherwise | **Contract Review** |
| cto `done` | **Ready for Dev** |
| dev `done`, `verify` PASS or SKIP | **Ready for QA** |
| dev `done`, `verify` PASS or SKIP, but `factory-pipeline`'s test merge conflicts; or a lane-base conflict before qa | **Ready for Dev** — a conflict round |
| dev `verify` FAIL, qa `route: ready_for_dev`, or an epic-verify `defect` | **Ready for Dev** — a defect round |
| qa `route: spec_done`, or an epic-verify `ambiguity` | **Spec Done** — an ambiguity round |
| qa `route: in_review` | **In Review** (an epic sub-issue: `factory-epic merge` moves it) |
| any other worker `done` | its Queue config's **success status** |
| dev `blocked`, `verify_blocked_reason: port-busy` | no move — retried or halted per `run-stage.md` **Port-busy** |
| any other `blocked`, `error`, or crash | no move — the ticket halts; run-stage **After a worker returns** already labelled it |

Make each move with `mcp__linear__save_issue`, passing the ticket `id`.

## Several lanes

When a stage runs in several lanes (`run-stage.md` **Repos and lanes**), act once every lane has returned, on the combined verdict:

- Any lane `blocked` (other than port-busy, which retries alone), `error` or crashed → the ticket halts.
- dev → **Ready for QA** only when every lane is `done` with PASS or SKIP; a lane's FAIL is a defect round.
- qa → `spec_done` if any lane routes it, else `ready_for_dev` if any does, else `in_review`.
