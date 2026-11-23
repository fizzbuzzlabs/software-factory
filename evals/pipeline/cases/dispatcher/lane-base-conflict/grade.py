from grading import check, hygiene

TICKET = "ACM-50"


def grade(run):
    branch = run.issue(TICKET)["gitBranchName"]
    briefs = [brief["prompt"] for brief in run.briefs("dev")]
    comments = "\n".join(run.comments(TICKET))
    return [
        check("dev ran despite the conflict", bool(run.worker_runs("dev", TICKET)), run.stages_run(TICKET)),
        check("the dev brief routes the lane-base conflict, naming the path",
              bool(briefs) and "Lane-base conflict" in briefs[0] and "src/app.txt" in briefs[0],
              briefs[0][-600:] if briefs else ""),
        check("a comment names the lane-base conflict and its path",
              "Lane-base conflict" in comments and "src/app.txt" in comments, comments[:400]),
        check("the ticket was never flagged needs attention", not run.ever_labelled(TICKET, "needs attention")),
        check("the ticket branch now contains main", run.merged_into("main", branch)),
        check("the ticket ends In Review", run.status(TICKET) == "In Review", run.status(TICKET)),
    ] + hygiene(run)
