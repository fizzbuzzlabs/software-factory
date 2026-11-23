from grading import check, hygiene, untouched

TICKET = "ACM-140"


def grade(run):
    branch = run.issue(TICKET)["gitBranchName"]
    pulls = run.pulls(head=branch, base="main", state="open")
    comments = "\n".join(run.comments(TICKET))
    return [
        check("dev ran once", run.stages_run(TICKET) == ["dev"], run.stages_run(TICKET)),
        check("ticket moved to Ready for QA", run.status(TICKET) == "Ready for QA", run.status(TICKET)),
        check("ticket has one open PR into main", len(pulls) == 1, [(p["head"], p["base"]) for p in run.pulls()]),
        check("the handoff comment links the PR", "/pull/" in comments, comments[:300]),
        check("no lifecycle label left", not {"in progress", "needs attention"} & set(run.labels(TICKET)),
              run.labels(TICKET)),
    ] + untouched(run, "ACM-141", "Ready for QA") + hygiene(run)
