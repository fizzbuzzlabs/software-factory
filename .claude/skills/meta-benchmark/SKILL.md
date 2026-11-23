---
name: meta-benchmark
description: "Re-test the factory: run a candidate version of its skills, conventions and agents and the version on main through the same pipeline evals (evals/pipeline) — dispatcher cases with stand-in workers, worker cases with real agents on a sample app, and, only when asked, real tickets replayed end to end — on one or more driver models, then report pass rates, per-principle scores, tokens and cost. Use for '/meta-benchmark', 'benchmark this branch against main', 're-test the factory', 'did this rewrite make the pipeline worse', 'which model should drive the pipeline'. Runs and reports only: never edits a skill, merges, or files tickets."
argument-hint: "[<candidate ref>] [--suite dispatcher | worker | e2e] [--model <id>...] [--case <glob>]"
---

# Meta — Benchmark

Find out whether a change to the factory's own instructions makes the pipeline better, worse or no different, by running both versions through the same cases. Every run makes real model calls on the user's account, so the job is to learn the most from the fewest runs.

## Required MCPs

None.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/factory-location.md`

## What there is to run

The harness is `<factory>/evals/pipeline`; its `README.md` covers the commands and how a case is built. An **arm** is one version of the factory, built into a plugin folder.

| Suite | What it tests | One run |
|---|---|---|
| `dispatcher` | What `/factory-pipeline` and `/factory-stage` do with tickets. Workers are stand-ins with scripted answers, so only the dispatcher's instructions and the driving model vary. | about $1–3, 1–4 min |
| `worker` | One real agent at one stage, on a seeded ticket in the sample app. Graded on what it pushed: the app's gates and controls, a replay of each commit, hidden requests, a blind judge. | about $0.50–1.30, 2–6 min |
| `e2e` | The whole pipeline with real workers, on a real ticket replayed in a sandbox clone of its app repo. | about $10, 40–55 min for a 7-behavior server ticket; capped by the case's budget |

## Steps

### 1. Build both arms

In `<factory>/evals/pipeline`:

```bash
python3 build_arm.py origin/main --name main
python3 build_arm.py <ref>                              # a committed candidate
python3 build_arm.py --worktree <name> [--from <path>]  # a candidate as it sits in a checkout
```

With no candidate named, the candidate is the current working tree. Then `diff -rq .arms/main/real-workers .arms/<candidate>/real-workers`: it must list only the files the change meant to touch.

### 2. Choose the smallest run that answers the question

- **Which suite.** A change to `factory-*`, `run-stage.md` or `stage-verdicts.md` is a dispatcher change. A change to an agent, a `workflow-*` skill or a convention a worker loads is a worker change. Run only the suite the diff touches.
- **Which model drives** is a dispatcher question: the same arm, once per `--model`.
- **How many runs.** One run per case per arm. More only where step 4 calls for it.
- **`e2e`** only when the user asks for it by name.

Before starting, say how many runs that is and roughly what they cost. Interactive: get a yes when it is more than about 40 runs or includes `e2e`. Headless: run the first pass only, never `e2e`.

### 3. Run

```bash
python3 run.py --arm main --model <id> --runs 1 --label <label>
python3 run.py --arm <candidate> --model <id> --runs 1 --label <label>
python3 run.py --suite worker --arm <arm> --runs 1 --label <label>
```

Run long batches in the background. When the runner prints `STOPPED`, the account's usage limit was hit: the runs after that point are void and never count. Report what finished and stop.

### 4. Read the failures before running more

A run fails when any one of its checks fails, so read which check, in which arm:

- **The same check fails in both arms** — a finding about the factory as it is, not about the change. Report it.
- **A check fails only in the candidate** — find the line the candidate cut or changed that the check depends on. That line is the result.
- **The arms differ on one run** — run that case once more on both arms. If it flips, it was noise.
- **A check looks wrong** — open the run's kept world. A broken grader or seed is fixed in the harness, and `regrade.py` grades the kept run again without a new one.
- **A `judge:` check** is a model's verdict and moves between regrades of the same work. Alone, it is weak evidence.

### 5. Report

`python3 compare.py <label>...` prints the table. Report in chat, never to Linear:

- per suite and arm: cases passing, checks passing, cost and time;
- for worker runs, the per-principle table;
- each difference between the arms, with its cause or "noise";
- findings about the current factory, kept apart from findings about the change;
- what the cases don't cover: sibling lanes, interactive mode, and (for worker cases) the worktree boundary guard;
- a recommendation.

## Real tickets (`e2e`)

A case replays a ticket that already shipped. The sandbox is a local clone of the app repo, rewound to before the ticket, whose `origin` is a local bare repo; Linear and GitHub are fakes. Nothing reaches the real boards or GitHub.

- The app's checkout must sit beside the factory's main checkout, or under `EVAL_APP_REPOS`.
- Workers have to boot the app to verify. Set `EVAL_APP_ENV` to the app's env file only when the user says to; the sandbox gets a symlink. Never read or print that file.
- `--dry` builds the sandbox and stops before any model call. Do that first.
- Run one arm at a time, and report the first run's measured cost before starting the second.
- Grade one run at a time, with no pipeline run in flight: the app's tests share one database, and a second load makes unrelated tests fail.
- The judge reads each success criterion of the spec against the diff, and its verdict on the same diff changes between reads. `regrade.py --suite e2e` reads it again; count a criterion as missed only when most of three reads say so.
- The two arms write different contracts, so a defect QA finds in one says nothing about the other. To compare them, boot both builds and send the same input.
- A good case is a ticket that went through the review pool, touched one repo, and needs no migration, no UI and no live model call to verify. Its `case.json` names the app, the ticket, its `workflows/` folder, the `Pool:` merge commit on the app's `main`, and under `before_tests` whatever the app's CI runs before its tests, such as a client build.

## Rules

- Never edit `.claude/skills/**` or `.claude/agents/**`, never merge, and never file a ticket from here. A finding goes in the report.
- Never count a void run, and never rerun a case just to turn a failure green.
- Never start `e2e`, a second model or a second run of every case on your own initiative.
