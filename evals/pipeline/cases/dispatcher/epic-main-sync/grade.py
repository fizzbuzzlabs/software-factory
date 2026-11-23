from grading import check, hygiene

EPIC, SLICES = "ACM-290", ["ACM-291", "ACM-292"]


def grade(run):
    branch = run.issue(EPIC)["gitBranchName"]
    return [
        check("the epic branch now contains main", run.merged_into("main", branch)),
        check("main was merged in, not rebased", not run.forced_pushes(), run.forced_pushes()),
        check("both slices are still on the epic branch",
              all(run.merged_into(run.issue(key)["gitBranchName"], branch) for key in SLICES)),
        check("no worker ran: nothing waits at a stage", not run.worker_runs(), run.worker_runs()),
        check("the epic was never flagged needs attention", not run.ever_labelled(EPIC, "needs attention")),
    ] + hygiene(run)
