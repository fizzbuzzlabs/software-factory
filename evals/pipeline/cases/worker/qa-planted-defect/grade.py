import json

from grading import check
from worker_grading import gates, shipped


def grade(run):
    handback = run.handback()
    checks = shipped(run)
    gate_checks, _ = gates(run, names=("typecheck", "lint"))
    checks += gate_checks
    suite_code, suite_output = run.gate("test")
    production = [path for path in run.changed_files()
                  if path.startswith("src/") and not path.endswith(".test.ts")]
    fixed, _, _ = run.replay("whitespace.json")
    findings = json.dumps(handback.get("findings", "")).lower()
    named = any(word in findings for word in ("whitespace", "blank", "trim", "spaces", "empty"))
    plan = run.read("workflows/%s/test-plan.md" % run.folder) or ""
    return checks + [
        check("route handed back is ready_for_dev", handback.get("route") == "ready_for_dev", handback.get("route")),
        check("the finding names the title rule that fails on rename", named, findings[:400]),
        check("a red test for the defect was pushed (the suite fails)", suite_code != 0, suite_output[-400:]),
        check("qa changed no production code", not production, production),
        check("the defect is still there: qa did not fix it", not fixed),
        check("test-plan.md was pushed", "## " in plan, run.changed_files()),
    ]
