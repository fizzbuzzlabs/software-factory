import { stableSortBy } from "../normalize.js";
import { list, text } from "../parse.js";
import { runScannerCli } from "./run-cli.js";

export interface MadgeResult {
  circularDependencyCount: number;
  cycles: string[][];
}

const PRODUCTION_ROOTS = ["src"];

export function runMadge(repoRoot: string): MadgeResult {
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
  const raw = list(JSON.parse(stdout), "madge's output").map((cycle) =>
    list(cycle, "a madge cycle").map((file) => text(file, "a madge cycle member")),
  );
  const cycles = stableSortBy(raw, (cycle) => cycle.join(","));
  return {
    circularDependencyCount: cycles.length,
    cycles,
  };
}
