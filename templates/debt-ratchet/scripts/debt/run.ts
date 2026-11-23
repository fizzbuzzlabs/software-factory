/**
 * Tech-debt gate orchestrator — runs the real scanners (jscpd, madge,
 * knip), normalizes their output into a canonical report, and writes it to
 * the gitignored `reports/debt/` directory. Reruns on an unchanged tree
 * are byte-identical.
 *
 *   npm run debt                   scan and write reports/debt/report.json (+ summary)
 *   npm run debt:check             scan and fail (exit 1) if either headline number
 *                                   (duplication %, circular-dependency count) regressed
 *                                   past debt-baseline.json
 *   npm run debt:baseline:update   scan and overwrite debt-baseline.json with the
 *                                   current headline numbers — the deliberate,
 *                                   documented path to lower the ratchet after paying
 *                                   down debt
 *
 * DEBT_BASELINE_PATH overrides the baseline file location (test isolation
 * only — mirrors EVAL_RUNS_DIR in tests/eval-exit-code.test.ts).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { compareToBaseline, readBaseline, writeBaseline, type DebtBaseline } from "./baseline.js";
import { assembleReport, renderSummary } from "./report.js";
import { runJscpd } from "./scanners/jscpd.js";
import { runKnip } from "./scanners/knip.js";
import { runMadge } from "./scanners/madge.js";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));
const OUTPUT_DIR = join(REPO_ROOT, "reports/debt");
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
  const summary = renderSummary(report);

  mkdirSync(OUTPUT_DIR, { recursive: true });
  writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2) + "\n");
  writeFileSync(SUMMARY_PATH, summary);
  console.log(summary);

  const current: DebtBaseline = {
    duplicationPercent: report.jscpd.duplicationPercent,
    circularDependencyCount: report.madge.circularDependencyCount,
  };

  if (isUpdateBaseline) {
    writeBaseline(BASELINE_PATH, current);
    console.log(`[debt] baseline updated: ${BASELINE_PATH}`);
    return;
  }

  if (isCheck) {
    const baseline = readBaseline(BASELINE_PATH);
    const verdict = compareToBaseline(current, baseline);
    if (!verdict.pass) {
      console.error(
        `[debt:check] ratchet regression —\n${verdict.reasons.map((r) => `  - ${r}`).join("\n")}`,
      );
      process.exit(1);
    }
    console.log("[debt:check] ratchet OK — no regression against baseline.");
  }
}

// Run only when invoked directly (not when imported by tests) — mirrors
// scripts/generate-css-tokens.ts.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
