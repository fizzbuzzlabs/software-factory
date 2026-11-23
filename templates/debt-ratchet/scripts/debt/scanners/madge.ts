/**
 * madge adapter — shells out to the real madge CLI over the production
 * import graph (src/, client/src/, shared/, resolved against the repo's
 * root tsconfig) and normalizes its circular-dependency output into
 * stable, repo-relative cycles.
 *
 * madge reports cycle members at file granularity (not line — it doesn't
 * expose the importing line number), and exits 1 (not an error — its own
 * CLI "found cycles" gate) whenever any cycle is found; both are handled
 * below so only a genuine scan failure throws.
 *
 * PRODUCTION_ROOTS below is this repo's production-source layout — the one
 * per-repo value in this file. Set it to THIS repo's source roots when you
 * install the ratchet (see templates/debt-ratchet/README.md step 4).
 */
import { stableSortBy } from "../normalize.js";
import { runScannerCli } from "./run-cli.js";

export interface MadgeResult {
  circularDependencyCount: number;
  cycles: string[][];
}

const PRODUCTION_ROOTS = ["src", "client/src", "shared"];

/** Run madge over the production import graph and return normalized, stably-sorted cycles. */
export function runMadge(repoRoot: string): MadgeResult {
  // madge exits 0 when no cycles are found, 1 when it finds at least one —
  // both are a successful scan; only another status is a real failure.
  const { stdout } = runScannerCli(
    "madge",
    repoRoot,
    [
      "--circular",
      "--json",
      "--extensions",
      "ts",
      "--ts-config",
      "tsconfig.json",
      ...PRODUCTION_ROOTS,
    ],
    [0, 1],
  );
  const raw = JSON.parse(stdout) as string[][];
  const cycles = stableSortBy(raw, (cycle) => cycle.join(","));
  return {
    circularDependencyCount: cycles.length,
    cycles,
  };
}
