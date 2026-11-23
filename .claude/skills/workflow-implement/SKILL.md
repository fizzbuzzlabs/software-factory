---
name: workflow-implement
description: "Implement features via TDD tracer bullets from contract.md. RED/GREEN/REFACTOR per behavior, committing and auto-continuing after each passing behavior, then verifies the change at its real surface — a PASS or SKIP verdict ships the code to the ticket's PR and moves the ticket to Ready for QA."
argument-hint: "[ABC-123 | project-folder] [--headless]"
---

# Implement

Build the contract one behavior at a time, test first, and ship only what you have seen work at its real surface.

## Required MCPs

- linear

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md`
- `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`
- `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md`
- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`
- `${CLAUDE_SKILL_DIR}/../conventions/worktree-isolation.md`

## What you read

`contract.md` in the project folder (resolve it per `${CLAUDE_SKILL_DIR}/../conventions/resolve-project-folder.md`). No contract → stop; `/workflow-contract` comes first. Read `research.md` for where things go and `design.md` when a behavior is unclear.

The contract's `## Behaviors` checklist is your queue: `[ ]` is pending, `[x]` is done. Start from the first `[ ]`.

**When reality contradicts the contract**, say what you expected, what you found and why it matters. Interactive: ask how to proceed. Headless: take the resolution that best honors the design's intent, and record the mismatch and your decision under `## Notes` in `contract.md`.

## A lane-base conflict

When your brief's **Routed findings** carry a lane-base conflict, your branch can't take its lane base cleanly. Before anything else, `git merge <lane base>` and resolve each conflicting file so both sides' behaviors hold: yours per your contract, the other side's per the contracts of the tickets that changed those lines on the lane base (`git log <lane base> -- <path>` names them). Commit the merge, run the full suite and fix what fails. When no resolution keeps both sides' behaviors, `git merge --abort`, ship nothing, and report the paths and why. The merge unticks nothing: with no other finding routed, a finished contract goes on to REFACTOR and the gates, so verify sees the merged code.

## One behavior at a time

Never write all the tests first. For each pending behavior, in order:

1. **RED** — one failing test that proves the behavior through its public interface, titled after the behavior. Run it and see it fail for the right reason.
2. **GREEN** — the least code that passes it. While iterating, run only the tests the change touches; go to the full suite mid-cycle only when the change crosses module boundaries or touches shared code.
3. **Is it really done?** A behavior that involves a user interaction or crosses a network or process boundary is done only when a passing test exercises that seam: a real dispatched interaction, or a real HTTP or process call. A test one layer below doesn't close it. A behavior that can reject or silently drop a user's action also has to make that visible, with the reason, through the project's own logging; if the project has none, say so instead of inventing one.
4. **Why-tests** — mutation-check each test that pins a constraint it never went red on, per `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`.
5. **Commit** — tick the behavior in `contract.md` and commit the code, its test and the contract as `<TICKET> behavior N: <behavior name>`, with a `mutation-checked:` line for any why-test. Never commit on the default branch. Then go straight on to the next behavior.

After the last behavior, **REFACTOR**: remove duplication and clean up with the tests green, run the full suite, and commit the cleanup on its own.

All code and tests follow `${CLAUDE_SKILL_DIR}/../conventions/code-writing.md`, and every **Implement** line in `${CLAUDE_SKILL_DIR}/../conventions/change-principles.md` binds.

## Coming back to a finished contract

A contract with every behavior ticked, on a ticket in Ready for Dev, was sent back: something failed after you shipped, and going straight to REFACTOR would ship nothing over a finding that is still red. Find what came back, in the ticket's comments and in your brief's **Routed findings** (a sibling lane's only source):

- **A QA finding** — a routed defect in a QA comment: an id, a `test file › title`, a contract clause, one line. Its RED is that committed QA test, failing for the finding's reason. Add a test at the behavior's seam when the QA test sits below it.
- **A human send-back** — a person's account of what failed when they tried the ticket in the app: `factory-pool remove`'s comment with its reason, or a comment on an epic slice someone moved back. It counts only when posted after the branch's last commit. Its RED is a new test at the seam that reproduces what the reason describes. A send-back with no reason, one no behavior covers, or one whose test passes against the current code → stop, ship nothing, and report the reason word for word.

Untick the behavior each one maps to and run the normal cycle from there. Nothing came back → the work is done; go to REFACTOR.

## Lanes

When your brief names a **Lane**, your queue is only the behaviors tagged `repo: <lane>`. What you know of the other lane is the contract's **Seam** and what you can read in your context worktrees (`${CLAUDE_SKILL_DIR}/../conventions/worktree-isolation.md`). Regenerate the Seam's generated files from the home context with the home repo's generator; never edit them by hand.

In a sibling lane the contract is read-only in the home context: don't tick it or add `## Notes`, and put a mismatch in your hand-back's assumptions. Nothing tells you a lane behavior is done except a `<TICKET> behavior N:` commit on your branch whose test still passes and still matches the clause.

## Before you ship

The full suite ran in REFACTOR. Then each of these, once:

1. **Static gate** — the project's lint, typecheck and build, as its CI runs them or as its `package.json` scripts name them. Run only commands the repo defines; never guess one. Fix failures in the code, never by loosening lint or compiler settings.
2. **Seam gate** — the project's seam-check command, if it has one.
3. **Debt-ratchet gate** — the project's debt check, if it has one. A regression is fixed by removing the duplication or cycle the change added, never by raising the committed baseline, which only a human moves.
4. **Verify gate** — always invoke the repo's `verify` (Skill tool) over the branch's commits with `--ticket <ticket-id>` in its arguments, even for a diff you judge tests-only or docs-only. `verify` lands its evidence on the ticket even under your brief's **Orchestrator mode** line. The verdict is whatever `verify` returns; only `verify` may say SKIP. PASS or SKIP clears the gate. FAIL → fix and verify again. Never count a check of your own as a verdict.
5. **Architecture sync** — after PASS or SKIP, invoke `workflow-show-changes` (Skill tool) with the ticket id. It never blocks the ship.
6. **Ship** per `${CLAUDE_SKILL_DIR}/../conventions/ship-artifact.md` with `artifact: code`, `target status: Ready for QA`, or `none` under your brief's **Orchestrator mode** line, returning the verify verdict.

A gate that two rounds of fixes don't clear stops the run with the PR unopened: report where it stopped. So does any verify outcome that isn't PASS, SKIP or FAIL: BLOCKED, an unknown verdict, or a `verify` the Skill tool won't run (the repo needs its own). One exception: BLOCKED for `port-busy` is a clash over ports, not a problem with the change. Ship commit-only (`target status: none`) so a retry resumes at these gates, and report `verify_blocked_reason: port-busy` beside the verdict.

End with a summary: behaviors completed, test status, commits, the verify verdict as `verify` returned it, and any assumptions.
