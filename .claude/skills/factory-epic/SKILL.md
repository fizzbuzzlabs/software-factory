---
name: factory-epic
description: "Integrate an epic for factory-pipeline — `sync <epic-id>` merges origin/main into the epic branch so it keeps up with main; `merge <slice-id>` lands a QA-green epic sub-issue's branch on its epic branch and moves the sub-issue to In Review; `finish <epic-id>` confirms every sub-issue is merged, verifies the epic branch, and opens or updates the epic's own PR to main. Use for '/factory-epic finish ABC-123' (retry a finish by hand), '/factory-epic sync ABC-123'; factory-pipeline invokes all three. Not building the slices (factory-pipeline) or the review pool (factory-pool)."
argument-hint: "sync <epic-id> | merge <slice-id> | finish <epic-id>"
user_invocable: true
---

# Factory — epic branch

An **epic** is a Linear issue with sub-issues; each sub-issue is a **slice**. The epic branch is the epic ticket's `gitBranchName`, under the same name in every repo it reaches. Slices merge into it one by one, and the whole epic reaches `main` through one PR per repo that a human merges.

An epic's **epic repos** are home plus each sibling (`${CLAUDE_SKILL_DIR}/../conventions/run-stage.md` **Repos and lanes**) where `origin/<epic-branch>` exists. A slice's **slice repos** are home plus each sibling where `origin/<slice-branch>` exists. A slice repo without the epic branch is a misconfiguration: halt the slice with `needs attention` and a comment naming the repo.

## Required MCPs

- linear
- github

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`

Every git write works in a temporary worktree per repo (`${CLAUDE_SKILL_DIR}/../factory-pool/SKILL.md` **Work in a temporary worktree**), never the session's own checkout. A rejected push to the epic branch means it moved: merge `origin/<epic-branch>` in and push again, once.

## sync <epic-id>

Leave the epic branch containing `origin/main` in every epic repo. An epic labelled `in progress` (another run is finishing it) or `needs attention` (halted) is skipped: report it and stop.

- In each epic repo where `origin/main` isn't an ancestor of the epic branch, merge it in with `--no-ff` and the message `Merge origin/main into epic <EPIC-ID>`, never a rebase, and push. Each repo has its own `main`, so a clean merge pushes even when another repo conflicts. A push rejected twice: report that repo as not synced.
- A conflict only in derived or generated files is resolved per `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md` **Resolve conflicts**, then pushed. Any other conflict halts the epic: abort, leaving that repo's epic branch as it was, add `needs attention` to the epic ticket, and comment:

  ```
  **Main-sync conflict** — merging `origin/main` into `<epic-branch>` conflicts in `<repo>`:
  - `<path>`
  Merge and resolve it by hand, then remove `needs attention`.
  ```

  Its slices keep building on the epic branch as it is.

Report each repo as merged, already current, conflicted, or not synced.

## merge <slice-id>

Leave the slice's branch merged into the epic branch in every slice repo, and the slice **In Review**.

- Merge with `--no-ff` and the message `Merge slice <SLICE-ID> into epic <EPIC-ID>`. Merge in every slice repo before pushing any, so a slice lands in all of them or none. A repo where the slice is already an ancestor of the epic branch needs nothing.
- Resolve a conflict per `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md`. An ambiguous one leaves the slice out of every repo: undo the merges not yet pushed, add `needs attention`, and comment the repo and the conflicting files.
- A push rejected twice halts the slice the same way.
- A slice that was sent back and is now merged again gets a fresh block on the epic's review ticket (delete its old one), so its boxes start empty.

## finish <epic-id>

Leave one open PR, epic branch → `main`, in each epic repo, a review ticket a human can walk through, and the epic ticket **In Review**. When any slice is not Canceled, In Review or Done, say so and stop; that is not an error. Nor is an epic carrying `needs attention`, halted until a human clears it: report it with the reason its latest comment gives, and stop.

Then claim the epic ticket (`${CLAUDE_SKILL_DIR}/../factory-stage/SKILL.md` **Lifecycle labels**).

1. **Every finished slice's code is on the epic branch.** Check by ancestry in each slice repo. A Done slice already on `origin/main` stays Done. A slice that is In Review or Done but not on the epic branch halts the finish, with no PR: its `Fixes` line would close a ticket whose code never landed. Any other Done slice was set Done too early: move it back to **In Review** so the review ticket and `Fixes` lines cover it.
2. **Sync architecture** in each epic repo and push what it committed (`${CLAUDE_SKILL_DIR}/../factory-pool/SKILL.md` **Sync architecture**).
3. **Verify the assembled epic** in each epic repo, home first, over `origin/main...<epic-branch>`, with the epic ticket as the evidence ticket and a sibling's server running from the home epic tree. Handle the verdict per `${CLAUDE_SKILL_DIR}/../conventions/integrate-branch.md`; any FAIL stops the finish with no PR.
   - **It bisects to one slice** — comment the repo and the failure on the slice, and report it as `<SLICE-ID>: defect | ambiguity — <failure>`: `defect` when the slice's contract decides the failing behavior and the code breaks it, `ambiguity` when the contract leaves it open. Run by hand rather than by `factory-pipeline`, also add `needs attention` to the slice.
   - **It doesn't** — add `needs attention` to the epic ticket and comment the repo and the failure.
4. **The PR** in each epic repo: ready for review, not draft, because CI skips drafts. Its body, in order: `Merge with a merge commit, not squash or rebase.`; `Fixes <review ticket>`; one `Fixes <SLICE-ID>` line per slice merged in that repo, in the order of its `Merge slice` commits on the epic branch (a `Merge origin/main into epic` commit is no slice); and, with more than one epic repo, **Paired epic PRs** linking the others. After sibling PRs are up, re-run each sibling's `check` on the home epic PR.
5. **The review ticket**, covering every epic repo's PR. Reuse or create it per `${CLAUDE_SKILL_DIR}/../factory-pool/SKILL.md` **Review ticket**: one `create-ticket` call carrying every field, label `review-pool` and `relatedTo` included. Its entries are the slices, so `relatedTo` lists every slice, never the epic. Only these differ:
   - title `Review epic <EPIC-ID> — <epic title>`, in the epic's project;
   - top line `Epic PR: <link per epic repo> · Epic verify: <verdict per repo> @ <short tip sha> · video`, the `video` linking the epic ticket's latest `verifier-web` comment;
   - footer `To send back a slice that failed your check: comment what went wrong on it and move it to Ready for Dev.`
6. Move the **epic ticket** to **In Review**.

Report the epic PR per repo, the slices each carries, and each repo's verify verdict, or why it stopped.

## Rules

- Never merge an epic PR or push to `main`.
- An epic PR lands as a merge commit, never a squash or rebase: "is this slice on `main`" is tested by ancestry, and either would make a correct Done slice look early.
- Never reset or rebuild a pushed epic branch: the home one carries the slice specs `workflow-questions` wrote. The only undo is of merges not yet pushed.
