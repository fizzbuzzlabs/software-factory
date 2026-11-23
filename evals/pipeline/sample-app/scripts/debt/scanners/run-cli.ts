import { spawnSync } from "node:child_process";
import { join } from "node:path";

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
      `[debt/${binaryName}] scan failed (exit ${String(result.status)}): ${result.stderr || result.stdout}`,
    );
  }
  return { stdout: result.stdout, stderr: result.stderr };
}
