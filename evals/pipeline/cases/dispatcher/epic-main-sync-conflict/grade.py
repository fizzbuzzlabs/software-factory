from grading import check, hygiene

EPIC = "ACM-290"


def grade(run):
    branch = run.issue(EPIC)["gitBranchName"]
    comments = "\n".join(run.comments(EPIC))
    return [
        check("the epic is flagged needs attention", "needs attention" in run.labels(EPIC), run.labels(EPIC)),
        check("the comment names the main-sync conflict and its path",
              "Main-sync conflict" in comments and "src/app.txt" in comments, comments[:400]),
        check("the epic branch was left as it was", not run.pushes_to(branch), run.pushes_to(branch)),
        check("no epic PR was opened", not run.pulls(head=branch), [(p["head"], p["base"]) for p in run.pulls()]),
        check("the epic was not moved", run.statuses_seen(EPIC) == ["Todo"], run.statuses_seen(EPIC)),
    ] + hygiene(run)
