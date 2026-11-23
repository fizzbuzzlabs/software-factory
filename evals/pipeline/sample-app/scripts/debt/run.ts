import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { stdoutLogger } from "../../src/kernel/logger.js";
import { compareToBaseline, readBaseline, writeBaseline, type DebtBaseline } from "./baseline.js";
import { assembleReport, renderSummary } from "./report.js";
import { runJscpd } from "./scanners/jscpd.js";
import { runKnip } from "./scanners/knip.js";
import { runMadge } from "./scanners/madge.js";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));
const OUTPUT_DIR = "reports/debt";
const REPORT_PATH = join(OUTPUT_DIR, "report.json");
const SUMMARY_PATH = join(OUTPUT_DIR, "summary.md");
const BASELINE_PATH = process.env.DEBT_BASELINE_PATH ?? join(REPO_ROOT, "debt-baseline.json");

function main(): void {
  const args = process.argv.slice(2);
  const isCheck = args.includes("--check");
  const isUpdateBaseline = args.includes("--update-baseline");

  const jscpd = runJscpd(REPO_ROOT);
  const madge = runMadge(REPO_ROOT);
  const knip = runKnip(REPO_ROOT);
  const report = assembleReport({ jscpd, madge, knip });

  mkdirSync(join(REPO_ROOT, OUTPUT_DIR), { recursive: true });
  writeFileSync(join(REPO_ROOT, REPORT_PATH), JSON.stringify(report, null, 2) + "\n");
  writeFileSync(join(REPO_ROOT, SUMMARY_PATH), renderSummary(report));

  const current: DebtBaseline = {
    duplicationPercent: report.jscpd.duplicationPercent,
    circularDependencyCount: report.madge.circularDependencyCount,
  };
  stdoutLogger.log("debt_scanned", {
    ...current,
    unusedExportCount: report.knip.unusedExportCount,
    summary: SUMMARY_PATH,
  });

  if (isUpdateBaseline) {
    writeBaseline(BASELINE_PATH, current);
    stdoutLogger.log("debt_baseline_updated", { baseline: BASELINE_PATH });
    return;
  }

  if (isCheck) {
    const verdict = compareToBaseline(current, readBaseline(BASELINE_PATH));
    if (!verdict.pass) {
      for (const reason of verdict.reasons) {
        stdoutLogger.log("debt_check_failed", { reason });
      }
      process.exit(1);
    }
    stdoutLogger.log("debt_check_passed", { baseline: BASELINE_PATH });
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
