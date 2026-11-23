/**
 * jscpd adapter — shells out to the real jscpd CLI scoped to production code
 * only (`src/`, `client/src/`, `shared/`; tests/evals/scripts/drizzle are
 * excluded, see contract Anti-Behaviors and design decision 3) and
 * normalizes its JSON report into stable, repo-relative clone findings.
 *
 * jscpd's own report embeds a detection timestamp and per-format durations
 * (its raw non-determinism); we read only the count/line/clone fields below,
 * so that run metadata never reaches the canonical report.
 *
 * PRODUCTION_SCAN_IGNORE below encodes this repo's production-vs-non-production
 * layout — the one per-repo value in this file. Set its excludes to THIS
 * repo's non-production directories when you install the ratchet (see
 * templates/debt-ratchet/README.md step 4).
 */
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { roundPercent, stableSortBy } from "../normalize.js";
import { runScannerCli } from "./run-cli.js";

export interface JscpdClone {
  firstFile: string;
  firstLine: number;
  secondFile: string;
  secondLine: number;
  lines: number;
  tokens: number;
}

export interface JscpdResult {
  totalLines: number;
  duplicatedLines: number;
  duplicationPercent: number;
  clones: JscpdClone[];
}

// Everything outside the production roots (src/, client/src/, shared/) —
// mirrors the contract's jscpd scope exclusions (tests/, evals/, scripts/,
// drizzle/) plus the repo's other non-production top-level directories.
const PRODUCTION_SCAN_IGNORE = [
  "**/node_modules/**",
  "**/.claude/**",
  "**/.codex/**",
  "**/.git/**",
  "**/.github/**",
  "**/client/app/**",
  "**/docs/**",
  "**/drizzle/**",
  "**/evals/**",
  "**/scripts/**",
  "**/skills/**",
  "**/tests/**",
  "**/workflows/**",
].join(",");

interface RawJscpdDuplicate {
  firstFile: { name: string; startLoc: { line: number } };
  secondFile: { name: string; startLoc: { line: number } };
  lines: number;
  tokens: number;
}

interface RawJscpdReport {
  duplicates: RawJscpdDuplicate[];
  statistics: { total: { lines: number; duplicatedLines: number; percentage: number } };
}

/** Run jscpd over the production roots and return normalized, stably-sorted clones. */
export function runJscpd(repoRoot: string): JscpdResult {
  const outDir = mkdtempSync(join(tmpdir(), "debt-jscpd-"));
  try {
    runScannerCli("jscpd", repoRoot, [
      ".",
      "--format",
      "typescript",
      "--ignore",
      PRODUCTION_SCAN_IGNORE,
      "--reporters",
      "json",
      "--output",
      outDir,
      "--silent",
    ]);
    const raw = JSON.parse(
      readFileSync(join(outDir, "jscpd-report.json"), "utf8"),
    ) as RawJscpdReport;

    const clones: JscpdClone[] = raw.duplicates.map((dup) => ({
      firstFile: dup.firstFile.name,
      firstLine: dup.firstFile.startLoc.line,
      secondFile: dup.secondFile.name,
      secondLine: dup.secondFile.startLoc.line,
      lines: dup.lines,
      tokens: dup.tokens,
    }));

    return {
      totalLines: raw.statistics.total.lines,
      duplicatedLines: raw.statistics.total.duplicatedLines,
      duplicationPercent: roundPercent(raw.statistics.total.percentage),
      clones: stableSortBy(
        clones,
        (c) => `${c.firstFile}:${c.firstLine}:${c.secondFile}:${c.secondLine}`,
      ),
    };
  } finally {
    rmSync(outDir, { recursive: true, force: true });
  }
}
