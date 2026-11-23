from grading import check, hygiene


def grade(run):
    defect_briefs = [brief["prompt"] for brief in run.briefs("dev") if "ACM-82" in brief["prompt"]]
    checks = [
        check("ACM-80: a FAIL verdict sent it back to dev, not on to qa",
              run.stages_run("ACM-80") == ["dev", "dev", "qa"], run.stages_run("ACM-80")),
        check("ACM-81: an ambiguity went to the architect, whose ready_for_qa skipped cto and dev",
              run.stages_run("ACM-81") == ["qa", "architect", "qa"], run.stages_run("ACM-81")),
        check("ACM-81 passed through Spec Done", run.statuses_seen("ACM-81")
              == ["Ready for QA", "Spec Done", "Ready for QA", "In Review"], run.statuses_seen("ACM-81")),
        check("ACM-82: a defect went to dev, then back to qa",
              run.stages_run("ACM-82") == ["qa", "dev", "qa"], run.stages_run("ACM-82")),
        check("ACM-82 passed through Ready for Dev", run.statuses_seen("ACM-82")
              == ["Ready for QA", "Ready for Dev", "Ready for QA", "In Review"], run.statuses_seen("ACM-82")),
        check("ACM-82's dev brief carries qa's finding", bool(defect_briefs) and "DEF-9" in defect_briefs[0],
              defect_briefs[0][-400:] if defect_briefs else "no dev brief for ACM-82"),
    ]
    for key in ("ACM-80", "ACM-81", "ACM-82"):
        checks += [
            check("%s ends In Review" % key, run.status(key) == "In Review", run.status(key)),
            check("%s carries no lifecycle label" % key,
                  not {"in progress", "needs attention"} & set(run.labels(key)), run.labels(key)),
        ]
    return checks + hygiene(run)
