from grading import check, hygiene

EPIC, SLICE = "ACM-20", "ACM-21"
RULES = ["never a bare array", "lists/access"]


def grade(run):
    checks = []
    for worker in ("architect", "cto"):
        briefs = [brief["prompt"] for brief in run.briefs(worker) if SLICE in brief["prompt"]]
        carried = bool(briefs) and all(rule in briefs[0] for rule in RULES)
        checks.append(check("%s brief carries the epic's cross-cutting rules" % worker, carried,
                            briefs[0][-600:] if briefs else "no %s brief found" % worker))
    epic_branch = run.issue(EPIC)["gitBranchName"]
    checks += [
        check("slice ran every stage once, in order", run.stages_run(SLICE) == ["architect", "cto", "dev", "qa"],
              run.stages_run(SLICE)),
        check("slice ends In Review", run.status(SLICE) == "In Review", run.status(SLICE)),
        check("slice is merged into the epic branch", run.merged_into(run.issue(SLICE)["gitBranchName"], epic_branch)),
        check("slice was built on the epic branch, not main",
              run.origin_file(run.issue(SLICE)["gitBranchName"],
                              "workflows/%s/epic.md" % run.scenario["tickets"][EPIC]["folder"]) is not None),
    ]
    return checks + hygiene(run)
