import os

from grading import check
from worker_grading import judged, sections, shipped


def grade(run):
    folder = "workflows/" + run.folder
    contract = run.read(folder + "/contract.md") or ""
    code_touched = [path for path in run.changed_files() if not path.startswith("workflows/")]
    handback = run.handback()
    checks = shipped(run) + [
        check("the reviewed contract was pushed", run.pushed() and folder + "/contract.md" in run.changed_files(),
              run.changed_files()),
        check("the cto wrote no code", not code_touched, code_touched),
        check("hand-back is done, with assumptions", handback.get("status") == "done" and "assumptions" in handback,
              sorted(handback)),
        check("the contract still has its sections",
              all(name in sections(contract) for name in ["Behaviors", "Modules", "Testing Decisions", "Anti-Behaviors"]),
              sorted(sections(contract))),
    ]
    with open(os.path.join(run.case_dir, "rubric.md")) as handle:
        rubric = handle.read()
    spec = run.read(folder + "/spec.md") or ""
    return checks + judged(run, "review", rubric, "### spec.md\n\n%s\n\n### contract.md after review\n\n%s"
                           % (spec, contract))
