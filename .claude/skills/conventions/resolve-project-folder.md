# Convention: Resolve Project Folder

How a `workflow-*` skill turns its first argument into a `workflows/<project>/` folder. Resolve in this order; first match wins.

Project folders are named `workflows/YYYY-MM-DD-<ticket-lowercase>-<slug>/`, so the ticket id is recoverable from the folder name — and the folder from the ticket id — with no Linear read.

## Resolution

1. **A folder that exists** — the argument matches `workflows/<argument>/`. Use it.
2. **A Linear ticket id** — the argument matches `[A-Za-z]+-\d+` (e.g. `ABC-123`). Match `workflows/*-<ticket-lowercase>-*/` — with Glob, or `find workflows -maxdepth 1 -type d -name '*-<ticket-lowercase>-*'` when Glob isn't in your tool list:
   - exactly one match → use it.
   - none → stop and report that no workflow folder exists for the ticket yet (the upstream skill that creates it hasn't run).
   - more than one → ask which (interactive), or pick the one with the newest `YYYY-MM-DD` prefix and log the choice under `## Assumptions` (headless).
3. **Neither** — no usable argument. Auto-detect recent `workflows/` folders and offer them (interactive), or stop and report that a folder or ticket id is required (headless).

Once resolved, the skill's own artifact checks (`spec.md` present? `contract.md` present?) apply against the chosen folder.

**In a sibling lane** (your brief's **Lane** is not the repo holding `workflows/`), glob under the home context worktree the brief names: `<home context>/workflows/*-<ticket-lowercase>-*/`. That folder is read-only (`worktree-isolation.md`). A file your stage writes, like `test-plan.md`, goes in `workflows/<that folder name>/` under your own root.
