import json
import re

from grading import check
from worker_grading import gates, sections, shipped


def grade(run):
    handback = run.handback()
    checks = shipped(run)
    gate_checks, _ = gates(run, names=("typecheck", "lint"))
    checks += gate_checks
    production = [path for path in run.changed_files()
                  if path.startswith("src/") and not path.endswith(".test.ts")]
    plan = run.read("workflows/%s/test-plan.md" % run.folder) or ""
    findings_section = sections(plan).get("Findings", "")
    blocking = [line for line in findings_section.splitlines()
                if "blocking" in line.lower() and re.search(r"snooz", line, re.I)]
    findings = json.dumps(handback.get("findings", "")).lower()
    names_gap = "snooz" in findings and any(word in findings for word in ("again", "already", "re-snooz", "second",
                                                                           "twice", "resnooz"))
    return checks + [
        check("route handed back is spec_done", handback.get("route") == "spec_done", handback.get("route")),
        check("the finding names snoozing an already-snoozed reminder", names_gap, findings[:500]),
        check("test-plan.md records it as a blocking ambiguity", bool(blocking), findings_section[:500]),
        check("qa changed no production code", not production, production),
    ]
