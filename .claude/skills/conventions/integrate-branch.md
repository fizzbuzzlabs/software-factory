# Convention: Integrate Branch

How a skill that merges several tickets' branches onto one shared branch (`factory-pool`'s review pool, `factory-epic`'s epic branch) resolves merge conflicts and verifies the result. The calling skill owns what happens to a ticket left out: its label, comment, and status.

## Resolve conflicts

- **Derived/generated file** (lockfiles, generated schema/migrations, `docs/architecture.html`, built assets): take neither side — re-run the file's generator (`npm install` for the lockfile, the repo's codegen or architecture-sync command, etc.), then stage the regenerated result. Resolve the derived-file list and its regeneration commands from the app repo's `CLAUDE.md` and `package.json` scripts, not from memory.
- **Numbered generated file** (two tickets both added migration `0049`): keep the shared branch's file and number, renumber the ticket's own with the repo's tool, regenerate what derives from it, and run the repo's checks over the result. A check that fails leaves the ticket out.
- **Hand-written source, intent-determinate**: when the involved tickets' workflow artifacts (`spec.md`, `contract.md`, `design.md`) and Linear comments together fix the correct combined result beyond doubt, resolve the conflict to match that intent and stage it. Record the resolution in the `--no-ff` merge commit message — the files touched and a one-line rationale — so the branch's PR surfaces it for review. **Verify the assembled whole** is the gate: a hand-resolution that fails to compose is dropped like any other merge.
- **Hand-written source, ambiguous**: when the artifacts don't cover the conflicting region, or leave the combined behavior open — common when two branches edit the same code and neither ticket decided their interaction — do NOT guess. `git merge --abort` and leave the ticket out.

## Verify the assembled whole

After the merges, run the app repo's `verify` skill (Skill tool) once over the shared branch. Per-branch green CI does not prove the set composes.

- **PASS**, or **SKIP** (nothing to drive) → the branch is promotable.
- **FAIL** → bisect: the offender is the newest merge whose removal makes verify pass again. Hand it back to the calling skill to take out, then re-verify until green.
- Anything else — BLOCKED, an unknown verdict, or a `verify` the Skill tool won't run (rejected, e.g. Claude Code's built-in `/verify` answering because the repo has none) → stop: no bisect, no ticket marked, no PR opened or updated; report the verdict or quoted rejection.

Never substitute a hand-rolled check.
