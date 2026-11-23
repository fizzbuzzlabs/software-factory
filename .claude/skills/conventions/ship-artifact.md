# Convention: Ship Artifact

The handoff the `workflow-*` skills use to ship an artifact on the ticket's one branch. A skill that closes a pipeline stage also opens the PR and advances the Linear ticket; a mid-stage checkpoint (`research.md`, `design.md`) only commits and pushes.

**Steps 3–5 — the PR, its ready flip, the status move and the comment — run only when a person invoked the skill directly.** A dispatched worker's brief carries `run-stage.md`'s **Orchestrator mode** line: it ships with `target status: none` and returns its verdict, and the dispatcher owns the handoff. No stage merges to `main`; the whole branch merges once, by a human, when the ticket reaches its review status. Runs the same in interactive and headless mode — the shipping steps are mechanical, so never gate them behind `AskUserQuestion`. The calling skill has already finalized the artifact's *contents* before invoking this; whether a human reviews them before the ship or on the shipped file is the caller's choice.

The caller supplies:

- **artifact** — the file this stage produced (e.g. `spec.md`, `contract.md`), or `code` when the stage's output is already committed across TDD commits.
- **target status** — the exact Linear status name to move the ticket to (resolve it via `list_issue_statuses`; match names case-insensitively), or `none` for **commit-only mode** (see Steps).
- **target branch** *(optional)* — the branch to commit, push, and PR onto; defaults to the ticket's own `gitBranchName`. A caller shipping an epic sub-issue's artifact onto its shared **epic branch** passes the epic's `gitBranchName` here; the status move and comment still target the sub-issue ticket.

## Which repo

The planning artifacts — `spec.md`, `research.md`, `design.md`, `contract.md`, the `design/` bundle — ship to the home repo (`run-stage.md` **Repos and lanes**), even when the ticket's code lands only in a sibling. Code ships to the repo you run in, on the ticket's one branch name. A sibling-lane worker ships only in its own repo: its `test-plan.md` goes in its own `workflows/<folder>/` beside the tests it maps, and it never writes the home folder.

## Resolve the ticket

From the project folder name `workflows/YYYY-MM-DD-<ticket>-<slug>/`, take `<ticket>` as the Linear identifier (e.g. `abc-1` → `ABC-1`). If the folder name carries no ticket id, read the artifact's `**Source:**` field for the ticket URL. No ticket resolvable → skip the Linear steps (status move + comment) and say so in the summary; still commit, push, and open/reuse the PR on a descriptive feature branch, naming it.

## The ticket branch

Every artifact lives on **one branch** — the **target branch** when the caller supplied one, else the ticket's canonical Linear branch (`gitBranchName` from `mcp__linear__get_issue`, e.g. `jdoe/abc-79-…`), created from `main` at the first ship. Before committing, be on it, one command per call:

```bash
git fetch origin
git switch <branch>
```

If the switch fails because the branch exists neither locally nor on `origin`, create it: `git switch --no-track -c <branch> origin/main`. Never commit an artifact to `main`.

## Steps

When **target status** is `none` (**commit-only mode**), run **steps 1–2 only** and skip steps 3–5 — the PR, the status move, and the comment belong to a later stage or the dispatcher; this run only lands its commits. Every other value runs all five steps.

1. **Commit.** Stage the artifact (for `artifact: code`, the TDD commits already exist — stage nothing new) and commit with a message naming the stage and ticket, per the repo's commit conventions.
2. **Push** the branch (`git push origin <branch>`, never `-u`: it writes the `.git/config` parallel workers share, per `worktree-isolation.md`). `origin` is the sole handoff between stages — one may run locally, the next in the cloud — so skipping the push strands this stage's output.
3. **Open or reuse the PR** via the managed GitHub MCP, not the `gh` CLI (absent in the cloud sandbox). If the branch already has an open PR (`mcp__github__list_pull_requests`, `head: <owner>:<branch>`), the push already updated it — reuse it; otherwise `mcp__github__create_pull_request` against `main` with `draft: true`, its body linking the `workflows/<project>/` folder (the home repo's, from a sibling lane). When **target status** is `In Review`, mark the PR ready (`mcp__github__update_pull_request`, `draft: false`); any other status leaves its draft state alone. Consuming repos run CI only on ready PRs, so a stage that skips this leaves the PR with no CI for review or the review pool.
4. **Advance the ticket.** Move it to **target status** via `mcp__linear__save_issue`, passing the ticket `id` — omit the id and Linear creates a new issue instead of updating.
5. **Comment** the handoff on the ticket with `mcp__linear__save_comment`: this stage's pushed commit `<branch>@<sha>` — a commit URL (`https://github.com/<owner>/<repo>/commit/<sha>`) when you can form one — and the PR URL.

Report the pushed commit `<branch>@<sha>`, the PR URL, the branch, and the ticket's new status in the skill's closing summary.
