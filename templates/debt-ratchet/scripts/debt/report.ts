/**
 * Report assembler — builds the canonical `report.json` from the normalized
 * per-scanner finding sets. The three headline numbers (duplication %,
 * circular-dependency count, unused-export count) live on this object so
 * the summary renderer and the ratchet both read them from one place
 * instead of re-deriving them from raw scanner output.
 */
import type { JscpdResult } from "./scanners/jscpd.js";
import type { KnipResult } from "./scanners/knip.js";
import type { MadgeResult } from "./scanners/madge.js";

export interface DebtReport {
  jscpd: JscpdResult;
  madge: MadgeResult;
  knip: KnipResult;
}

export function assembleReport(input: {
  jscpd: JscpdResult;
  madge: MadgeResult;
  knip: KnipResult;
}): DebtReport {
  return {
    jscpd: input.jscpd,
    madge: input.madge,
    knip: input.knip,
  };
}

// Cap on how many findings per category the one-page summary cites — a
// "top findings" digest, not the full raw dump (report.json carries that).
const TOP_FINDINGS_LIMIT = 10;

/**
 * Render the one-page Markdown summary from an assembled report: the three
 * headline numbers plus top findings, every finding citing repo-relative
 * `file:line` (cycles at file granularity — see contract Assumptions).
 * Pure function of `report`, so it reruns byte-identical alongside
 * report.json.
 */
export function renderSummary(report: DebtReport): string {
  const lines: string[] = [];
  lines.push("# Tech Debt Report", "");
  lines.push(
    `- Duplication: ${report.jscpd.duplicationPercent}% (${report.jscpd.duplicatedLines}/${report.jscpd.totalLines} lines)`,
  );
  lines.push(`- Circular dependencies: ${report.madge.circularDependencyCount}`);
  lines.push(`- Unused exports: ${report.knip.unusedExportCount}`);
  lines.push("", "## Top findings", "");

  lines.push("### Duplication (jscpd)", "");
  if (report.jscpd.clones.length === 0) {
    lines.push("- none");
  } else {
    for (const clone of report.jscpd.clones.slice(0, TOP_FINDINGS_LIMIT)) {
      lines.push(
        `- ${clone.firstFile}:${clone.firstLine} <-> ${clone.secondFile}:${clone.secondLine} (${clone.lines} lines)`,
      );
    }
  }
  lines.push("");

  lines.push("### Circular dependencies (madge)", "");
  if (report.madge.cycles.length === 0) {
    lines.push("- none");
  } else {
    for (const cycle of report.madge.cycles.slice(0, TOP_FINDINGS_LIMIT)) {
      lines.push(`- ${cycle.join(" -> ")}`);
    }
  }
  lines.push("");

  lines.push("### Unused exports (knip)", "");
  if (report.knip.exports.length === 0) {
    lines.push("- none");
  } else {
    for (const finding of report.knip.exports.slice(0, TOP_FINDINGS_LIMIT)) {
      lines.push(`- ${finding.file}:${finding.line} ${finding.name}`);
    }
  }
  lines.push("");

  return lines.join("\n");
}
