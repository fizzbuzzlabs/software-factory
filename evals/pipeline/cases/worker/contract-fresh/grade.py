import os
import re

from grading import check
from worker_grading import judged, sections, shipped

NEEDED = ["Behaviors", "Modules", "Testing Decisions", "Anti-Behaviors"]


def grade(run):
    folder = "workflows/" + run.folder
    contract = run.read(folder + "/contract.md") or ""
    found = sections(contract)
    footprint = found.get("Footprint", "")
    behaviors = re.findall(r"^\s*\d+\.\s*\[ \]", found.get("Behaviors", ""), re.M)
    code_touched = [path for path in run.changed_files() if not path.startswith("workflows/")]
    handback = run.handback()
    checks = shipped(run) + [
        check("contract.md was pushed", bool(contract), run.changed_files()),
        check("research.md and design.md were pushed with it",
              bool(run.read(folder + "/research.md")) and bool(run.read(folder + "/design.md")), run.changed_files()),
        check("contract has every required section", all(name in found for name in NEEDED), sorted(found)),
        check("behaviors are an ordered checklist, all unchecked", len(behaviors) >= 4, len(behaviors)),
        check("contract has a Footprint naming the repo and the source paths it touches",
              "`reminders`" in footprint and "src/" in footprint and "workflows/" not in footprint,
              footprint[:300]),
        check("with nothing in flight, the hand-back reports no dependency",
              handback.get("depends_on") in (None, "none", []), handback.get("depends_on")),
        check("the architect wrote no code", not code_touched, code_touched),
        check("hand-back is done, with assumptions and open questions",
              handback.get("status") == "done" and "assumptions" in handback and "open_questions" in handback,
              sorted(handback)),
    ]
    if contract:
        with open(os.path.join(run.case_dir, "rubric.md")) as handle:
            rubric = handle.read()
        spec = run.read(folder + "/spec.md") or ""
        checks += judged(run, "contract", rubric, "### spec.md\n\n%s\n\n### contract.md\n\n%s" % (spec, contract))
    return checks
