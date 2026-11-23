# Pipeline evals

Tests for the factory's own instructions. They answer one question: if a skill, convention or
agent file changes, does the pipeline still do the right thing?

Nothing here ships to app repos, and nothing here runs in CI: every run makes real model calls.

## Three suites

**Dispatcher cases** (`cases/dispatcher/`) test what `/factory-pipeline` and `/factory-stage` do
with tickets. The workers are stand-ins that return a scripted answer in seconds, so the only
thing that varies is the dispatcher's instructions and the model that drives it. Each case is one
situation with a known right outcome: a slice going green, a crashed worker's leftover worktree,
a port clash, a failing pool.

**Worker cases** (`cases/worker/`) test one real agent at one stage: `architect`, `cto`, `dev` or
`qa`, on one seeded ticket in the sample app. Each is graded on what it pushed: the app's own
gates and controls, a replay of each commit, hidden requests against the running service, and a
blind model judge for what a script can't tell.

**End-to-end cases** (`cases/e2e/`) replay a real ticket that already shipped: the whole pipeline, with real
workers, in a sandbox clone of the app repo rewound to just before the ticket. Graded on where the
ticket ended, the app's own gates on the ticket branch, and a blind judge reading each success
criterion of the spec against the diff. A run takes hours and is capped by the case's budget.

No suite can reach real systems. Linear and GitHub are fake MCP servers (`fakes/`), `origin`
is a local bare repo, and each session starts with a clean environment.

## Run it

An **arm** is one version of the factory, built into a plugin folder:

```bash
python3 build_arm.py origin/main --name main      # the factory at a git ref
python3 build_arm.py --worktree mine              # the factory as it is in this checkout
python3 build_arm.py --worktree mine --from ../other-checkout
```

Run cases against an arm, then compare arms:

```bash
python3 run.py --arm main --model claude-fable-5-2                  # every dispatcher case, 3 runs each
python3 run.py --arm mine --model claude-opus-5-5 --case 'epic-*' --runs 1
python3 run.py --suite worker --arm main --case 'build-*' --jobs 2  # real agents, on their own models
python3 run.py --suite e2e --arm main --model claude-opus-5-5 --dry  # build the sandbox, no model call
EVAL_APP_ENV=~/code/my-app/.env python3 run.py --suite e2e --arm main --model claude-opus-5-5 --runs 1
python3 compare.py                                                  # pass rates, tokens, cost, time
```

An end-to-end case needs the app's checkout beside the factory's main checkout (or under
`EVAL_APP_REPOS`). Workers boot the app to verify their work, so `EVAL_APP_ENV` names the app's env
file; the sandbox gets a symlink to it and nothing reads or copies it.

`run.py` prints each run as it finishes and names the checks that failed. Results land in
`results/<label>/`; a failed run's whole world is kept in the work directory (`EVAL_WORK_DIR`,
else the system temp dir) for a look, and `regrade.py <case> <run dir>` grades it again after a
grader changes.

A dispatcher run costs roughly $1–3 at API prices and takes one to four minutes. A worker run
costs more and takes 10 to 40 minutes.

## How a dispatcher case works

```
cases/dispatcher/<name>/
  seed.json    the tickets, their statuses, and what each stand-in worker will hand back
  setup.py     optional: extra state, such as a leftover worktree or a conflicting commit on main
  grade.py     grade(run) -> checks, read from the end state
```

`harness/scaffold.py` builds the run's world from the seed: a small repo (`fixture/`) pushed to a
local origin, the ticket branches and `workflows/` folders each status implies, and the fake
boards. The dispatcher session then runs there with the arm's plugin. Its stand-in workers run
`.dev/worker.sh <stage> <ticket>`, which re-homes onto the ticket branch, pushes the scripted
files, logs when it started and ended, and prints the scripted hand-back.

A grader reads outcomes, never the dispatcher's words: ticket statuses and labels over time,
comments, PRs, what is on `origin`, every push (and whether it was forced), worktrees left behind,
which workers ran and when, and the briefs they were given. `grading.hygiene` holds the checks
every case shares, such as nothing pushed to `main` and no PR merged.

## How a worker case works

```
cases/worker/<name>/
  case.json    stage, ticket, workflow folder, which code seeds and documents make up the start state
  seed/        files laid over the sample app, on main or on the ticket branch
  hidden/      request scripts the worker never sees
  grade.py     grade(run) -> checks
  rubric.md    optional: yes/no criteria for the judge
```

`sample-app/` is a small reminders service with the factory's own controls installed: the ESLint
and tsconfig template, the debt ratchet and the no-comments check. `cases/worker/_shared/code/`
holds code seeds several cases start from, such as a finished feature for QA to test.
`check_cases.py` builds every case's start state and runs the app's gates on it;
`check_overlay.py` does the same for one code seed.

The agent runs the way a sibling-lane worker does: a headless session in a worktree on the ticket
branch, briefed by `worker-brief.md` in orchestrator mode, so it pushes and hands back but opens
no PR and moves no ticket.

## How an end-to-end case works

```
cases/e2e/<name>/case.json   the app, the ticket, its workflows/ folder, the "Pool:" merge commit on the app's
                             main, and what the app's CI runs before its tests
```

`harness/e2e_scaffold.py` clones the app, checks out the commit the ticket branched from, drops the
`Sibling repos:` line and the installed-plugin settings, and pushes `main` and a ticket branch
holding only the original `spec.md` to a local bare origin. The dispatcher then runs
`/factory-pipeline <ticket>` there with the arm's real agents. `harness/e2e_grading.py` grades the
result and records how many times each stage ran and how big the change is next to what shipped.

A headless session waits only 10 minutes for a background worker before killing it, so the runner
lifts that ceiling (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`) for every run. The test check compares
against the test files that already fail on the commit before the ticket, so only a newly failing
file counts.

Pick a ticket that went through the review pool, touched one repo, and needs no migration, no UI
and no live model call to verify.

## Adding a case

Start from the outcome. Write down what must be true afterwards that would not be true if the
factory got it wrong, then make the smallest seed that puts the factory in that spot. A case
earns its place when doing nothing fails it (`tests/test_cases.py` checks that for dispatcher
cases) and when it checks an outcome a person would care about, not a step.

```bash
python3 -m unittest discover tests     # fakes, graders and seeds; no model calls
```
