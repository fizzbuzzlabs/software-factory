---
name: factory-pool
description: "Manage factory-pipeline's review pool — the long-lived `review-pool` branch where each QA-green standalone ticket lands as one merge commit, behind a single `review-pool → main` PR. `add` stacks In Review tickets on top, `remove <ticket>` takes one out by resetting to the commit before it and re-merging everything above it, `verify` syncs the pool's architecture diagram, checks the whole pool and refreshes the PR. Use for '/factory-pool remove ABC-123', '/factory-pool add', 'take ABC-123 out of the review pool'; factory-pipeline invokes it. Not epic branches (factory-epic)."
argument-hint: "add [<ticket-id>...] | remove <ticket-id>... [--to <status>] [--reason <text>] | verify"
user_invocable: true
---

# Factory — review pool

The pool is how a human reviews many finished tickets in one sitting. It is a stack on the `review-pool` branch, cut from `main`, behind one `review-pool → main` PR that only a human merges. Each entry is one `--no-ff` merge of a ticket branch, and its message ends in this trailer paragraph, which is how an entry is found again and replayed:

```
Pool: <TICKET-ID> <ticket title>

Pool-Ticket: <TICKET-ID>
Pool-Head: <the ticket-branch sha that was merged>
```

The two trailers stay together as the message's last paragraph, or the listing below loses the entry. The pool's entries, oldest first, as `<merge sha> <ticket> <pooled head sha>`:

```bash
git log --first-parent --merges --reverse --format='%H %(trailers:key=Pool-Ticket,valueonly,separator=) %(trailers:key=Pool-Head,valueonly,separator=)' origin/main..review-pool
```

Each repo, the home repo and every sibling (`${CLAUDE_SKILL_DIR}/../conventions/run-stage.md` **Repos and lanes**), has its own pool and pool PR. A ticket's **pool repos** are home plus each sibling where `origin/<gitBranchName>` exists. It enters and leaves all of them together, so everything below happens in each pool repo, and a ticket that can't enter one enters none.

## Required MCPs

- linear
- github

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`

## How the pool is kept

### Work in a temporary worktree

Every git write and every `verify` run happens in a temporary worktree at `<repo root>/.claude/worktrees/factory-<branch with / → ->`, never in the session's own checkout, and the worktree and its local branch are removed when the step ends, pass or fail. `<repo root>` is the main checkout even when the session runs in a linked worktree; a sibling's is its local path. If the branch is checked out somewhere else, change nothing and report that path.

### Is there a live pool?

The pool is live when a `review-pool → main` PR is open, or when `origin/review-pool` exists and no closed PR has its tip as head (a run crashed between push and PR). Then work on `origin/review-pool`. Otherwise the last pool was merged or closed, or there never was one: start a fresh pool from `origin/main`, and let its first push replace the old branch (`--force-with-lease` against the old tip).

Resolve the team and project scope per `${CLAUDE_SKILL_DIR}/../factory-stage/SKILL.md` (**Resolve IDs**).

### Conflicts

Resolve a merge conflict per `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md`, recording a hand-resolution above the trailer paragraph. An ambiguous one leaves the ticket out: abort, undo its merges in the other pool repos, add `needs attention`, comment the conflicting files, and strike it on the review ticket with `merge conflict: <files>`.

### Sync architecture

Invoke `workflow-show-changes` (Skill tool) with `--tree <tree>`. A skip or failure never blocks; carry its note into the report. Its commit is never a pool entry.

### Verify

Install dependencies and ensure services in the tree per `${CLAUDE_SKILL_DIR}/../conventions/worktree-isolation.md` (**Resolve dependencies after re-home**), then run that repo's `verify` once over `origin/main...<branch>`, and handle the verdict per **Verify the assembled whole** in `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md`.

- **Home** — invoke `verify` (Skill tool) with the tree path, the range and the **evidence ticket** (the review ticket, once one exists) in its arguments.
- **Sibling** — the home session can't load a sibling's skills, so start a headless session in the tree per run-stage **Launch** (sibling lane), with no `--agent`, asked to run the `verify` skill over the range and end with `{ "verdict": "<PASS | FAIL | SKIP | BLOCKED>", "reason": "<…>" }` on its last line. Its `<env>` points the server at the home pool's tree on port 3999, so the sibling pool is verified against the home pool.

### The pool PR

One open `review-pool → main` PR per pool repo, titled `Review pool`, ready for review, not draft, because CI skips drafts. Its body, in order:

- `Verify: <PASS | FAIL | SKIP | BLOCKED> @ <short tip sha>` from the pool's latest verify, with the reason for a SKIP or BLOCKED, or `Verify: not yet run`. Carry it forward when nothing re-verified, adding `(stale)` once the tip has moved past that sha.
- `Fixes <review ticket>`, then one `Fixes <TICKET-ID>` line per entry in pool order, and every hand-resolved conflict with its rationale. A ticket that isn't in the pool has no `Fixes` line: merging the PR would close it. A new pool's review ticket is created holding the PR's link, so open the PR without its `Fixes <review ticket>` line and add that line once the ticket exists.
- **Open ambiguities (noted, not blocking)** — each entry's `noted` `AMB-#` lines from its `test-plan.md`, for the reviewer to settle at merge. Omit when there are none.
- **Paired pools** — a link to every other repo's pool PR. Omit without siblings.

After a sibling's pool pushes, re-run its `Sibling repos:` `check` on the home pool PR, as run-stage does for a ticket.

### Review ticket

The human accepts the pool by walking each ticket through in the app, not by reading the PR. One review ticket covers every pool repo's PR. Reuse the one an open pool PR's `Fixes` line names, or one whose top line links such a PR. Otherwise create it with one `create-ticket` call (Skill tool) carrying every field below, none left to a later update: review tickets are found by their label.

- **title** `Review pool — <YYYY-MM-DD>`
- **label** `review-pool`
- **state** In Review
- **assignee** `me`
- **relatedTo** every entry, never as sub-issues; an entry joining a reused review ticket is related when it joins
- **description** the template below

```
Pool PR: <link per pool repo> · Pool verify: <verdict per repo> @ <short tip sha> · [video](<the review ticket's latest verifier-web comment>)

### <TICKET-ID> — [<title>](<ticket url>)
Evidence: verify <verdict> · [video](<that ticket's latest verifier-web comment>)
- [ ] <step in the app> → <expected result>

---
To remove a ticket that failed your check: `/factory-pool remove <TICKET-ID> --reason "what went wrong"`
```

- One block per entry. Its boxes are the `## Success Criteria` of the ticket's `spec.md` (no spec → its `contract.md`'s at-the-seam acceptance tests), each written as a step in the app and the result to expect.
- **Evidence** links the ticket's latest `verifier-web` comment (it opens `📹 **<TICKET-ID> verification — <verdict>**`); none → `Evidence: no recording`. Drop `video` from the top line while the review ticket has no such comment.
- A ticket that leaves the pool is **struck**: its block becomes the two lines below, and a comment `<TICKET-ID> removed: <reason>` goes on the review ticket. A ticket that comes back gets a fresh block with empty boxes.

  ```
  ### ~~<TICKET-ID> — <title>~~
  Removed: "<reason>" · back to <its status now>
  ```

The boxes are the human's alone: never tick one, and never rewrite the whole description, because the ticks live in it. Edit it with `save_issue` `patch`. Linear reflows markdown on save, so only single-line anchors match, and an anchor that matches twice fails the whole patch. It also stores a ticket id as `<issue id="…" label="<TICKET-ID>" href="…" />`, so read the description first and anchor on lines as stored: a block by its heading line carrying `label="<TICKET-ID>"`, the top line by `Pool PR:` (`Epic PR:` on an epic's), and put new blocks before the `---`.

## add [<ticket-id>...]

Stack each candidate on the pool, push, and refresh the PR and review ticket. Candidates are the given tickets, else every **In Review** ticket on the team in project scope, oldest `updatedAt` first. A candidate has no parent and no sub-issues, no `needs attention` or `review-pool` label, a branch on `origin`, and isn't already in the pool. A pooled ticket whose branch has moved since its `Pool-Head` is taken out and added again, with a fresh block.

Return the tickets added, skipped (with the reason), and left out for a conflict.

## remove <ticket-id>... [--to <status>] [--reason <text>]

Take the tickets out and leave the rest of the pool as it was:

- Rebuild from the commit before the earliest entry being removed, re-merging every later entry that stays, each at its listed `Pool-Head`. A replay that conflicts ambiguously drops that entry too.
- **Verify** the result before pushing.
- Push with `--force-with-lease` against the tip you started from. A rejected lease means the pool moved: start over.
- Move each removed ticket to `--to` (default **Ready for Dev**) and comment that it left the pool, with the reason. Left In Review, the next `add` would put it straight back. Delete its Linear attachment for the pool PR: the `Fixes` line leaves the body, but Linear keeps the link. Strike it on the review ticket with the reason, else `removed by hand`.
- Refresh the PR and the review ticket.

A ticket in no pool is reported and skipped.

## verify

An empty pool is reported and nothing else happens. Otherwise claim the review ticket (`${CLAUDE_SKILL_DIR}/../factory-stage/SKILL.md` **Lifecycle labels**).

Home first, then each sibling. **Sync architecture**, **Verify** the pool, push what the sync committed, and refresh the PR and review ticket.

On FAIL, take the bisected offender out as `remove` does, but leave it **In Review** with `needs attention` and a comment naming the repo and the failure, and strike it with `pool verify failed: <repo> — <failure>`.

## Rules

- Never merge the pool PR or push to `main`; the human's merge is the only write to `main`.
- Never rebuild the pool from `main` except to start a fresh one.
