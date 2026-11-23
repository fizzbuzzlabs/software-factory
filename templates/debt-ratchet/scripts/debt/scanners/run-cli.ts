/**
 * Shared scanner-invocation shape: spawn a scanner binary from
 * node_modules/.bin, and treat exit codes as "scan failure vs. clean scan
 * vs. scan found issues" per that scanner's own CLI gate semantics — knip
 * and madge both exit 1 when they find something to report, which is a
 * successful scan, not an error. Only an unexpected exit code throws.
 */
import { spawnSync } from "node:child_process";
import { join } from "node:path";

/**
 * Run `node_modules/.bin/<binaryName>` with `args` from `repoRoot`.
 * `allowedExitCodes` defaults to `[0]`; pass `[0, 1]` for scanners whose
 * CLI treats "found issues" as exit code 1.
 */
export function runScannerCli(
  binaryName: string,
  repoRoot: string,
  args: string[],
  allowedExitCodes: number[] = [0],
): { stdout: string; stderr: string } {
  const bin = join(repoRoot, "node_modules/.bin", binaryName);
  const result = spawnSync(bin, args, { cwd: repoRoot, encoding: "utf8" });
  if (!allowedExitCodes.includes(result.status ?? -1)) {
    throw new Error(
      `[debt/${binaryName}] scan failed (exit ${result.status}): ${result.stderr || result.stdout}`,
    );
  }
  return { stdout: result.stdout, stderr: result.stderr };
}
