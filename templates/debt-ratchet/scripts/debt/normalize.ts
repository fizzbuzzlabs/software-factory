/**
 * Determinism primitives shared by every scanner adapter and the report
 * assembler: repo-relative POSIX paths, stable sorting by a canonical key,
 * and fixed-precision percentage rounding. This is the one place that makes
 * `npm run debt` reruns byte-identical on an unchanged tree — see
 * scripts/debt/run.ts.
 */
import { relative, sep } from "node:path";

/** Convert an absolute or OS-native path to a repo-relative POSIX path. */
export function toRepoRelativePosix(inputPath: string, repoRoot: string): string {
  const rel = inputPath.startsWith(repoRoot) ? relative(repoRoot, inputPath) : inputPath;
  return rel.split(sep).join("/");
}

/**
 * Stable-sort items by a string key derived from each item. Node's
 * `Array.prototype.sort` is a stable sort (ES2019+), so equal keys keep
 * their input order — callers should make the key fully discriminating
 * whenever tie order matters for determinism.
 */
export function stableSortBy<T>(items: T[], keyFn: (item: T) => string): T[] {
  return [...items].sort((a, b) => {
    const ka = keyFn(a);
    const kb = keyFn(b);
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
}

/** Round a percentage to 2 decimals — the fixed precision the ratchet
 *  compares at, to avoid float jitter (contract behavior 5). */
export function roundPercent(value: number): number {
  return Math.round(value * 100) / 100;
}
