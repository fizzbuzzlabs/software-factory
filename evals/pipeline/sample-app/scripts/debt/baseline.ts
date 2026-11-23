import { readFileSync, writeFileSync } from "node:fs";
import { count, record } from "./parse.js";

export interface DebtBaseline {
  duplicationPercent: number;
  circularDependencyCount: number;
}

export interface RatchetVerdict {
  pass: boolean;
  reasons: string[];
}

const DUPLICATION_SLACK_PERCENT = 0.1;

export function readBaseline(baselinePath: string): DebtBaseline {
  const raw = record(JSON.parse(readFileSync(baselinePath, "utf8")), "the baseline");
  return {
    duplicationPercent: count(raw.duplicationPercent, "the baseline's duplicationPercent"),
    circularDependencyCount: count(raw.circularDependencyCount, "the baseline's circularDependencyCount"),
  };
}

export function writeBaseline(baselinePath: string, current: DebtBaseline): void {
  writeFileSync(baselinePath, JSON.stringify(current, null, 2) + "\n");
}

export function compareToBaseline(current: DebtBaseline, baseline: DebtBaseline): RatchetVerdict {
  const reasons: string[] = [];
  if (current.duplicationPercent > baseline.duplicationPercent + DUPLICATION_SLACK_PERCENT) {
    reasons.push(
      `duplication % regressed — baseline ${String(baseline.duplicationPercent)}% (+${String(DUPLICATION_SLACK_PERCENT)} slack), current ${String(current.duplicationPercent)}%`,
    );
  }
  if (current.circularDependencyCount > baseline.circularDependencyCount) {
    reasons.push(
      `circular-dependency count regressed — baseline ${String(baseline.circularDependencyCount)}, current ${String(current.circularDependencyCount)}`,
    );
  }
  return { pass: reasons.length === 0, reasons };
}
