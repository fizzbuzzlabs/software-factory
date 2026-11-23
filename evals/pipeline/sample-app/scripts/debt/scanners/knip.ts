import { stableSortBy } from "../normalize.js";
import { count, list, record, text, type JsonRecord } from "../parse.js";
import { runScannerCli } from "./run-cli.js";

interface KnipFileLine {
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

const EXPORT_ISSUE_TYPES = [
  "exports",
  "nsExports",
  "types",
  "nsTypes",
  "enumMembers",
  "namespaceMembers",
  "duplicates",
];
const DEPENDENCY_ISSUE_TYPES = ["dependencies", "devDependencies"];
const INCLUDE_ISSUE_TYPES = ["files", "dependencies", ...EXPORT_ISSUE_TYPES].join(",");

function findings(issue: JsonRecord, file: string, kinds: string[]): KnipFileLine[] {
  return kinds.flatMap((kind) =>
    list(issue[kind] ?? [], `knip's ${kind}`).map((entry) => {
      const item = record(entry, `a knip ${kind} entry`);
      return {
        file,
        line: item.line === undefined ? 0 : count(item.line, `a knip ${kind} line`),
        name: text(item.name, `a knip ${kind} name`),
      };
    }),
  );
}

export function runKnip(repoRoot: string): KnipResult {
  const { stdout } = runScannerCli(
    "knip",
    repoRoot,
    ["--config", "knip.json", "--include", INCLUDE_ISSUE_TYPES, "--reporter", "json"],
    [0, 1],
  );
  const raw = record(JSON.parse(stdout), "knip's output");

  const files: string[] = [];
  const exportsFindings: KnipFileLine[] = [];
  const dependencyFindings: KnipFileLine[] = [];

  for (const entry of list(raw.issues, "knip's issues")) {
    const issue = record(entry, "a knip issue");
    const file = text(issue.file, "a knip issue's file");
    for (const unused of list(issue.files ?? [], "knip's files")) {
      files.push(typeof unused === "string" ? unused : file);
    }
    exportsFindings.push(...findings(issue, file, EXPORT_ISSUE_TYPES));
    dependencyFindings.push(...findings(issue, file, DEPENDENCY_ISSUE_TYPES));
  }

  const uniqueFiles = stableSortBy([...new Set(files)], (f) => f);
  const sortedExports = stableSortBy(exportsFindings, (e) => `${e.file}:${String(e.line)}:${e.name}`);
  const sortedDependencies = stableSortBy(
    dependencyFindings,
    (d) => `${d.file}:${String(d.line)}:${d.name}`,
  );

  return {
    unusedExportCount: sortedExports.length,
    files: uniqueFiles,
    exports: sortedExports,
    dependencies: sortedDependencies,
  };
}
