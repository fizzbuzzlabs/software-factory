import re

from grading import check
from worker_grading import gates, replay_commits, shipped


def grade(run):
    handback = run.handback()
    checks = shipped(run)
    gate_checks, skipped = gates(run)
    checks += gate_checks
    passed, failures, _ = run.replay("filter.json")
    claimed, broken = replay_commits(run)
    everything = run.source(tests=True)
    survivors = sorted(path for path, text in everything.items() if re.search(r"\blist(All|Open)\b", text))
    production = run.source()
    self_filtering = sorted(path for path, text in production.items()
                            if "store" not in path and re.search(r"\.filter\(.*status", text))
    contract = run.read("workflows/%s/contract.md" % run.folder) or ""
    return checks + [
        check("hidden requests pass against the running app", passed, failures[:5]),
        check("listAll and listOpen are gone everywhere: no alias, wrapper or leftover caller", not survivors,
              survivors),
        check("no caller filters a full list by status itself", not self_filtering, self_filtering),
        check("one commit per behavior (3 behaviors)", len(claimed) >= 3, [c["subject"] for c in run.commits()]),
        check("the behaviors did not land as one lump: at least two behavior commits", len(claimed) >= 2,
              [c["subject"] for c in run.commits()]),
        check("every behavior commit is green on its own", not broken, broken[:3]),
        check("every behavior is ticked in contract.md", "[ ]" not in contract.split("## Modules")[0], ""),
        check("verify verdict handed back is PASS", handback.get("verify") == "PASS", handback.get("verify")),
        check("no test was skipped or left todo", not skipped, skipped[:3]),
    ]
