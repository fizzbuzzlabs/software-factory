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

const TOP_FINDINGS_LIMIT = 10;

export function renderSummary(report: DebtReport): string {
  const lines: string[] = [];
  lines.push("# Tech Debt Report", "");
  lines.push(
    `- Duplication: ${String(report.jscpd.duplicationPercent)}% (${String(report.jscpd.duplicatedLines)}/${String(report.jscpd.totalLines)} lines)`,
  );
  lines.push(`- Circular dependencies: ${String(report.madge.circularDependencyCount)}`);
  lines.push(`- Unused exports: ${String(report.knip.unusedExportCount)}`);
  lines.push("", "## Top findings", "");

  lines.push("### Duplication (jscpd)", "");
  if (report.jscpd.clones.length === 0) {
    lines.push("- none");
  } else {
    for (const clone of report.jscpd.clones.slice(0, TOP_FINDINGS_LIMIT)) {
      lines.push(
        `- ${clone.firstFile}:${String(clone.firstLine)} <-> ${clone.secondFile}:${String(clone.secondLine)} (${String(clone.lines)} lines)`,
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
      lines.push(`- ${finding.file}:${String(finding.line)} ${finding.name}`);
    }
  }
  lines.push("");

  return lines.join("\n");
}
