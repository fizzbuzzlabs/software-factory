import os
import re

from grading import check
from worker_grading import gates, judged, replay_commits, shipped


def grade(run):
    handback = run.handback()
    checks = shipped(run)
    gate_checks, skipped = gates(run)
    checks += gate_checks
    passed, failures, _ = run.replay("snooze.json")
    claimed, broken = replay_commits(run)
    contract = run.read("workflows/%s/contract.md" % run.folder) or ""
    production = run.source()
    timers = [path for path, text in production.items() if re.search(r"\bset(Timeout|Interval)\(", text)]
    checks += [
        check("hidden requests pass against the running app", passed, failures[:5]),
        check("one commit per behavior (6 behaviors)", len(claimed) >= 6, [c["subject"] for c in run.commits()]),
        check("the behaviors did not land as one lump: at least two behavior commits", len(claimed) >= 2,
              [c["subject"] for c in run.commits()]),
        check("every behavior commit is green on its own", not broken, broken[:3]),
        check("every behavior is ticked in contract.md", "[ ]" not in contract.split("## Modules")[0], ""),
        check("verify verdict handed back is PASS", handback.get("verify") == "PASS", handback.get("verify")),
        check("no timer ends a snooze", not timers, timers),
        check("no test was skipped or left todo", not skipped, skipped[:3]),
    ]
    with open(os.path.join(run.case_dir, "rubric.md")) as handle:
        rubric = handle.read()
    material = "\n\n".join("### %s\n%s" % item for item in sorted(production.items()) if "reminders/" in item[0])
    return checks + judged(run, "type", rubric, material)
