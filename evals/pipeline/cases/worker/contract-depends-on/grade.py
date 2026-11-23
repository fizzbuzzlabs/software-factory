import json

from grading import check
from worker_grading import sections, shipped

OTHER = "ACM-206"


def grade(run):
    folder = "workflows/" + run.folder
    contract = run.read(folder + "/contract.md") or ""
    research = sections(run.read(folder + "/research.md") or "").get("Depends On", "")
    handback = run.handback()
    depends = handback.get("depends_on")
    code_touched = [path for path in run.changed_files() if not path.startswith("workflows/")]
    return shipped(run) + [
        check("contract.md was pushed", bool(contract), run.changed_files()),
        check("research.md records the dependency on the snooze ticket", OTHER in research, research[:300]),
        check("the hand-back reports depends_on the snooze ticket",
              isinstance(depends, list) and any(OTHER in json.dumps(entry) for entry in depends), depends),
        check("the architect added no relation itself (the dispatcher links it)",
              not run.linear["issues"][run.ticket]["blockedBy"], run.linear["issues"][run.ticket]["blockedBy"]),
        check("the architect wrote no code", not code_touched, code_touched),
    ]
