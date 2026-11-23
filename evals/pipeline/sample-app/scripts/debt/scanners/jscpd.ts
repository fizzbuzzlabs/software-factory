import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { roundPercent, stableSortBy } from "../normalize.js";
import { count, list, record, text } from "../parse.js";
import { runScannerCli } from "./run-cli.js";

interface JscpdClone {
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

const PRODUCTION_SCAN_IGNORE = [
  "**/node_modules/**",
  "**/.git/**",
  "**/controls/**",
  "**/reports/**",
  "**/scripts/**",
  "**/*.test.ts",
  "**/*.config.ts",
].join(",");

function location(value: unknown, what: string): { name: string; line: number } {
  const file = record(value, what);
  return {
    name: text(file.name, `${what}'s name`),
    line: count(record(file.startLoc, `${what}'s startLoc`).line, `${what}'s start line`),
  };
}

function clone(value: unknown): JscpdClone {
  const duplicate = record(value, "a jscpd duplicate");
  const first = location(duplicate.firstFile, "a jscpd duplicate's firstFile");
  const second = location(duplicate.secondFile, "a jscpd duplicate's secondFile");
  return {
    firstFile: first.name,
    firstLine: first.line,
    secondFile: second.name,
    secondLine: second.line,
    lines: count(duplicate.lines, "a jscpd duplicate's lines"),
    tokens: count(duplicate.tokens, "a jscpd duplicate's tokens"),
  };
}

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
    const raw = record(
      JSON.parse(readFileSync(join(outDir, "jscpd-report.json"), "utf8")),
      "jscpd's report",
    );
    const total = record(record(raw.statistics, "jscpd's statistics").total, "jscpd's total");
    const clones = list(raw.duplicates, "jscpd's duplicates").map(clone);

    return {
      totalLines: count(total.lines, "jscpd's total lines"),
      duplicatedLines: count(total.duplicatedLines, "jscpd's duplicated lines"),
      duplicationPercent: roundPercent(count(total.percentage, "jscpd's duplication percentage")),
      clones: stableSortBy(
        clones,
        (c) => `${c.firstFile}:${String(c.firstLine)}:${c.secondFile}:${String(c.secondLine)}`,
      ),
    };
  } finally {
    rmSync(outDir, { recursive: true, force: true });
  }
}
