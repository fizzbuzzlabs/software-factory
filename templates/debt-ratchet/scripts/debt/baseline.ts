/**
 * Baseline / ratchet — reads, compares, and updates the committed
 * `debt-baseline.json`, producing a pass/fail verdict with a
 * human-readable reason naming the regressed metric and its
 * baseline-vs-current values, so a red gate is never indistinguishable
 * from a broken one.
 */
import { readFileSync, writeFileSync } from "node:fs";

export interface DebtBaseline {
  duplicationPercent: number;
  circularDependencyCount: number;
}

export interface RatchetVerdict {
  pass: boolean;
  reasons: string[];
}

// Duplication is allowed a small slack margin over baseline: real refactors
// jitter the percentage by fractions of a point (moving a block, renaming a
// symbol), and a strict ratchet would red-gate on that noise. The gate fails
// only when duplication rises MORE than this many points above baseline.
// Circular dependencies get no slack — a new cycle is always a regression.
const DUPLICATION_SLACK_PERCENT = 0.1;

export function readBaseline(baselinePath: string): DebtBaseline {
  return JSON.parse(readFileSync(baselinePath, "utf8")) as DebtBaseline;
}

export function writeBaseline(baselinePath: string, current: DebtBaseline): void {
  writeFileSync(baselinePath, JSON.stringify(current, null, 2) + "\n");
}

/**
 * Compare the current run's two headline numbers to baseline. Duplication %
 * fails only when it rises more than DUPLICATION_SLACK_PERCENT above
 * baseline; the circular-dependency count fails on any strict increase.
 * Passes when flat or improved. Duplication % is compared at the same fixed
 * 2-decimal precision the report already rounds to, to avoid float jitter
 * (contract behavior 5).
 */
export function compareToBaseline(current: DebtBaseline, baseline: DebtBaseline): RatchetVerdict {
  const reasons: string[] = [];
  if (current.duplicationPercent > baseline.duplicationPercent + DUPLICATION_SLACK_PERCENT) {
    reasons.push(
      `duplication % regressed — baseline ${baseline.duplicationPercent}% (+${DUPLICATION_SLACK_PERCENT} slack), current ${current.duplicationPercent}%`,
    );
  }
  if (current.circularDependencyCount > baseline.circularDependencyCount) {
    reasons.push(
      `circular-dependency count regressed — baseline ${baseline.circularDependencyCount}, current ${current.circularDependencyCount}`,
    );
  }
  return { pass: reasons.length === 0, reasons };
}
