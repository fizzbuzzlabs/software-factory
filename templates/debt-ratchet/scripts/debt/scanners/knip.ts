/**
 * knip adapter — shells out to the real knip CLI, driven by the committed
 * `knip.json` (every real entry point declared, `tsx`/`msw` suppressed as
 * intentionally-held dependencies), and normalizes its unused
 * files/exports/dependencies into stable `file:line` findings.
 *
 * Scope is deliberately narrower than a full knip run: only the "unused
 * code" issue types (files, exports and their sub-kinds, dependencies) —
 * not unlisted/unresolved/cycles, which are a different debt class (madge
 * already owns circular dependencies). knip exits 1 (not an error — its
 * own "found issues" CLI gate) whenever any issue is found; handled below
 * so a real finding isn't mistaken for a scan failure.
 */
import { stableSortBy } from "../normalize.js";
import { runScannerCli } from "./run-cli.js";

export interface KnipFileLine {
  file: string;
  line: number;
  name: string;
}

export interface KnipResult {
  unusedExportCount: number;
  files: string[];
  exports: KnipFileLine[];
  dependencies: KnipFileLine[];
}

// The "unused code" issue types (contract behavior 3): unused files, every
// exports sub-kind knip tracks, and unused dependencies. Deliberately
// excludes unlisted/unresolved/catalog*/cycles — a different debt class.
const EXPORT_ISSUE_TYPES = [
  "exports",
  "nsExports",
  "types",
  "nsTypes",
  "enumMembers",
  "namespaceMembers",
  "duplicates",
];
const INCLUDE_ISSUE_TYPES = ["files", "dependencies", ...EXPORT_ISSUE_TYPES].join(",");

interface RawKnipItem {
  name: string;
  line?: number;
}

interface RawKnipIssue {
  file: string;
  files?: RawKnipItem[] | string[];
  dependencies?: RawKnipItem[];
  devDependencies?: RawKnipItem[];
  [key: string]: unknown;
}

interface RawKnipReport {
  issues: RawKnipIssue[];
}

/** Run knip against the committed knip.json and return normalized, stably-sorted findings. */
export function runKnip(repoRoot: string): KnipResult {
  // knip exits 0 when clean, 1 when it finds issues — both are a
  // successful scan; only another status is a real failure.
  const { stdout } = runScannerCli(
    "knip",
    repoRoot,
    ["--config", "knip.json", "--include", INCLUDE_ISSUE_TYPES, "--reporter", "json"],
    [0, 1],
  );
  const raw = JSON.parse(stdout) as RawKnipReport;

  const files: string[] = [];
  const exportsFindings: KnipFileLine[] = [];
  const dependencyFindings: KnipFileLine[] = [];

  for (const issue of raw.issues) {
    for (const entry of issue.files ?? []) {
      // knip's own "files" issue type reports the unused file itself as
      // `issue.file` — the per-entry list here is a self-reference, not a
      // separate location, so read the file path off the issue.
      files.push(typeof entry === "string" ? entry : issue.file);
    }
    for (const kind of EXPORT_ISSUE_TYPES) {
      for (const entry of (issue[kind] as RawKnipItem[] | undefined) ?? []) {
        exportsFindings.push({ file: issue.file, line: entry.line ?? 0, name: entry.name });
      }
    }
    for (const entry of [...(issue.dependencies ?? []), ...(issue.devDependencies ?? [])]) {
      dependencyFindings.push({ file: issue.file, line: entry.line ?? 0, name: entry.name });
    }
  }

  const uniqueFiles = stableSortBy([...new Set(files)], (f) => f);
  const sortedExports = stableSortBy(exportsFindings, (e) => `${e.file}:${e.line}:${e.name}`);
  const sortedDependencies = stableSortBy(
    dependencyFindings,
    (d) => `${d.file}:${d.line}:${d.name}`,
  );

  return {
    unusedExportCount: sortedExports.length,
    files: uniqueFiles,
    exports: sortedExports,
    dependencies: sortedDependencies,
  };
}
