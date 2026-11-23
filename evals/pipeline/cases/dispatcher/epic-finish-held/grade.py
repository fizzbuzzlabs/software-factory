from grading import check, hygiene

EPIC, SLICES = "ACM-230", ["ACM-231", "ACM-232"]


def grade(run):
    epic_branch = run.issue(EPIC)["gitBranchName"]
    report = run.final_message()
    return [
        check("the report says the epic is held by another run",
              "held by another run" in report and EPIC in report, report[-600:]),
        check("no epic PR was opened", not run.pulls(head=epic_branch), [(p["head"], p["base"]) for p in run.pulls()]),
        check("nothing was pushed to the epic branch", not run.pushes_to(epic_branch), run.pushes_to(epic_branch)),
        check("the epic was not verified", not run.verify_log, run.verify_log),
        check("no review ticket was made", not run.issues_labelled("review-pool"),
              [issue["id"] for issue in run.issues_labelled("review-pool")]),
        check("the epic stays in Todo", run.statuses_seen(EPIC) == ["Todo"], run.statuses_seen(EPIC)),
        check("the epic keeps its in progress label", "in progress" in run.labels(EPIC), run.labels(EPIC)),
        check("no worker ran", not run.worker_runs(), run.worker_runs()),
    ] + [check("%s stays In Review" % key, run.statuses_seen(key) == ["In Review"], run.statuses_seen(key))
         for key in SLICES] + hygiene(run)
