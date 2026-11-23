# Tech-debt ratchet — per-repo install

A deterministic tech-debt gate: three scanners (jscpd duplication, madge circular
dependencies, knip unused code) normalized into one report, ratcheted against a
committed `debt-baseline.json`. `debt:check` fails when duplication rises past
baseline plus a small slack margin, or when the circular-dependency count rises at
all — so a duplication or cycle regression is caught before it merges.

This directory is a **template**, not a shipped package. It is not symlinked into the
installed factory plugin cache (the plugin ships only `plugin/skills|agents|hooks`);
you copy from a factory checkout, referenced as `$CLAUDE_FACTORY_REPO/templates/debt-ratchet`
(see step 6 of the factory's
[setup guide](../../docs/setup.md)).

Kept deliberately manual: steps 4 and 5 need human judgment per repo (which
directories are production source, and what the first honest baseline is).

## Files here

- `scripts/debt/` — the scanner adapters + orchestrator, portable and copied verbatim.
  Two constants carry this repo's production-source layout and must be set (step 4):
  `PRODUCTION_ROOTS` in `scripts/debt/scanners/madge.ts` and `PRODUCTION_SCAN_IGNORE`
  in `scripts/debt/scanners/jscpd.ts`.
- `knip.json` — knip config with `entry` / `project` as `TODO` placeholders. Do not
  copy another repo's layout values.
- `package.json.scripts` — the three script lines to paste into `package.json`.
- `ci-step.yml` — the `debt:check` CI step fragment.
- **No `debt-baseline.json`** — it is generated per-repo on the first run (step 5),
  never copied. Copying one in would pin the ratchet to another repo's numbers.

## Install (6 steps)

1. **Install the tools** as devDependencies:

   ```bash
   npm i -D jscpd knip madge tsx
   ```

2. **Copy the portable files in.** Copy `scripts/debt/` and `knip.json` from this
   template into the repo root, and add the reports output dir to `.gitignore`:

   ```
   reports/debt/
   ```

3. **Add the scripts.** Paste the three lines from `package.json.scripts` into the
   `scripts` block of the repo's `package.json`.

4. **Point the scanners at this repo's layout** (human judgment):
   - `knip.json` — replace the `TODO` `entry` and `project` placeholders with this
     repo's real entry points and source globs.
   - `scripts/debt/scanners/madge.ts` — set `PRODUCTION_ROOTS` to this repo's
     production source roots.
   - `scripts/debt/scanners/jscpd.ts` — set `PRODUCTION_SCAN_IGNORE` to exclude this
     repo's non-production directories.

5. **Generate the baseline** (human judgment). Run the scan once and read the summary;
   sanity-check that the duplication % and cycle count reflect real current state (not a
   misconfigured scope). Only then write the committed baseline:

   ```bash
   npm run debt                    # scan, print summary, write reports/debt/
   npm run debt:baseline:update    # commit this repo's own debt-baseline.json
   ```

   `debt:baseline:update` is the **only** sanctioned way to move the ratchet, and it is
   a deliberate human step — never automate it, or the gate can raise its own ceiling.

6. **Add the CI step.** Paste `ci-step.yml` into a job in `.github/workflows/*.yml`,
   after `npm ci`, so a regression that escapes the pre-PR gate still fails the merge.

Once `debt:check` exists as a script, the factory's `workflow-implement` runs it
automatically as a pre-PR gate; until then that gate no-ops.
