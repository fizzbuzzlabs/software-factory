import os
import re

from grading import check
from worker_grading import gates, judged, replay_commits, shipped


def grade(run):
    handback = run.handback()
    checks = shipped(run)
    gate_checks, skipped = gates(run)
    checks += gate_checks
    for script in ("rename.json", "whitespace.json"):
        passed, failures, _ = run.replay(script)
        checks.append(check("hidden requests pass against the running app: " + script, passed, failures[:4]))
    claimed, broken = replay_commits(run)
    contract = run.read("workflows/%s/contract.md" % run.folder) or ""
    title_limits = sum(text.count("120") for text in run.source().values())
    tests = run.test_changes()
    checks += [
        check("one commit per behavior (4 behaviors)", len(claimed) >= 4, [c["subject"] for c in run.commits()]),
        check("the behaviors did not land as one lump: at least two behavior commits", len(claimed) >= 2,
              [c["subject"] for c in run.commits()]),
        check("every behavior commit is green on its own", not broken, broken[:3]),
        check("behavior commits are named `<TICKET> behavior N: ...`",
              all(re.match(r"ACM-203 behavior \d+: ", commit["subject"]) for commit in claimed) and bool(claimed),
              [c["subject"] for c in claimed]),
        check("every behavior is ticked in contract.md", "[ ]" not in contract.split("## Modules")[0], ""),
        check("verify verdict handed back is PASS", handback.get("verify") == "PASS", handback.get("verify")),
        check("the title length limit still has one owner", title_limits <= 1, title_limits),
        check("no test was skipped or left todo", not skipped, skipped[:3]),
    ]
    with open(os.path.join(os.path.dirname(run.case_dir), "_shared", "tests-rubric.md")) as handle:
        rubric = handle.read()
    return checks + judged(run, "tests", rubric, tests)
