---
name: bootstrap-controls
description: "Install a principle's control in the current repo, existing or new, without enforcing everything at once. 1. Agree what counts as a violation by running audit-principles interactively. 2. Install the control's check in CI with today's violations recorded in a baseline, so only new ones fail. 3. Open that install as its own PR. 4. Propose a Linear epic for the refactor: each slice removes violations and records the smaller baseline, and the last slice makes the emptied rules strict. Run once per control; on a repo that already has it, it says so and stops. Use for '/bootstrap-controls group-by-feature', 'bootstrap group-by-feature in this repo', 'install the group-by-feature control'. Does NOT do the refactor (the pipeline builds the epic) or report where a repo stands (audit-principles)."
argument-hint: "<control> [--headless | --interactive]"
---

# Bootstrap Controls

Install a control once: agree what counts as a violation, stop new violations with a baselined check, and plan the burn-down as an epic. Each supported control is a module folder, `${CLAUDE_SKILL_DIR}/controls/<control>/`, whose `CONTROL.md` owns what it installs, its CI wiring, verification, close-out and slicing; read it in full first. In a module, `<skills>` means `${CLAUDE_SKILL_DIR}/..`.

A **baseline** is the committed list of known violations and ratchet numbers, and it may only shrink. The control's check fails on a violation that isn't on the list, so nothing new gets in. It fails on a list entry that no longer occurs, so a fixed violation must come off the list and can't come back. It fails on a list that grew compared with the base branch, so nobody adds to it by hand. A **ratchet** is a measured number that may only go down.

## Required MCPs

- linear
- github

Run the preflight as **Step 0**, per `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`

## Steps

### 1. Resolve the control

Detect the mode per `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`. The argument names a folder under `${CLAUDE_SKILL_DIR}/controls/`; missing or unknown, list the folders and ask (headless: stop with the list). The control is **installed** when the default branch has `controls/<control>/config.json` and a CI step that runs its check. Installed: say so and stop. Point the user at `audit-principles` for where the repo stands, and say whether the repo's `check.py` differs from the audit module's; updating it is its own ticket.

### 2. Audit and agree (interactive only)

Invoke `audit-principles` with the control's principle and `--interactive`. It works through the audit with the user and returns two things:

- the config the user approved, written to the repo but not committed
- the audit report

In headless mode, stop instead: only the user can agree what counts as a violation, and the install depends on it.

### 3. Install

On a branch `controls/<control>-install` off the default branch, follow CONTROL.md's Install and Verify. If the repo has no CI workflow that runs on pull requests, stop and say so. Fix any violation of a rule agreed `strict` in this PR, or ask to make that rule `baseline`; never baseline a `strict` rule's violation. Change no other feature code. Commit, push, and open a draft PR via the GitHub MCP, its body holding the report's table and the baseline's size. Don't merge it.

### 4. Create the refactor epic

Skip when nothing is baselined and every ratchet is at zero; say so. Otherwise draft an epic from the report: the score, the counts, and its slices per CONTROL.md's Slices, one per refactor target plus a close-out slice. Show it to the user. On approval, create the epic and each slice via `create-ticket`, then link each slice with `save_issue` (update): `parentId` the epic, and the close-out slice `blockedBy` every other slice.

### 5. Report

```
## bootstrap-controls: <control> in <repo>
Score: <from the audit report>
Installed: <PR link>
Strict: <rules>   Baselined: <rule: count, ...>   Ratchets: <name: number, ...>
Epic: <identifier and link, or why none>   Slices: <identifiers>
Next: merge the install PR; spec each slice; /epic-review-specs <epic>; /factory-pipeline <epic>
Controls not yet installed here: <other folders under controls/>
```

### 6. Spec the slices

Invoke `workflow-questions` with each slice's identifier in turn, the close-out slice last. The user may stop after any slice; name the slices left unspecced.

## Rules

- The install PR and the refactor never share a PR.
- Tightening lands through the epic's slices, never a second run of this skill.
- A new control is a new module folder, `CONTROL.md` with Install, Verify, Close-out, Slices and Why not a setting sections, plus an audit module for its principle in `audit-principles`. Why not a setting has one row per rule and ratchet in the module's `check.py`: the closest ESLint, tsconfig or SwiftLint setting (`templates/eslint`, `templates/swiftlint`, or the Swift settings in `docs/controls.md`) and what it misses. A rule a setting fully covers goes in the setting, not `check.py`.
