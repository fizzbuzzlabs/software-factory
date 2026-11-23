import os
import re

from grading import check
from worker_grading import judged, sections, shipped


def grade(run):
    folder = "workflows/" + run.folder
    handback = run.handback()
    contract = run.read(folder + "/contract.md") or ""
    changed = run.changed_files()
    other = [path for path in changed if path not in (folder + "/contract.md", folder + "/design.md")]
    diff = run.diff(folder + "/contract.md").splitlines()
    touched = [line for line in diff if re.match(r"^[+-](?![+-])", line)]
    route = handback.get("route")
    behaviors = sections(contract).get("Behaviors", "")
    reopened = "[ ]" in behaviors
    checks = shipped(run) + [
        check("the amended contract was pushed", folder + "/contract.md" in changed, changed),
        check("nothing but the contract (and design) changed: no code, no test plan", not other, other),
        check("the amendment is surgical (at most 30 changed lines)", 0 < len(touched) <= 30, len(touched)),
        check("route handed back is contract_review or ready_for_qa", route in ("contract_review", "ready_for_qa"),
              route),
        check("a behavior that must change is unticked exactly when the route sends it back to be built",
              reopened == (route == "contract_review"), "route=%s, unticked=%s" % (route, reopened)),
        check("the six original behaviors are still there", len(re.findall(r"^\d+\. \[", behaviors, re.M)) >= 6,
              behaviors[:300]),
    ]
    with open(os.path.join(run.case_dir, "rubric.md")) as handle:
        rubric = handle.read()
    return checks + judged(run, "amendment", rubric, "### contract.md after the amendment\n\n" + contract)
