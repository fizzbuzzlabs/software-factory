from grading import check, hygiene

FIRST, LATER = "ACM-250", "ACM-251"


def grade(run):
    comments = "\n".join(run.comments(LATER))
    return [
        check("the first ticket ends In Review", run.status(FIRST) == "In Review", run.status(FIRST)),
        check("the later ticket's dev ran once", len(run.worker_runs("dev", LATER)) == 1, run.stages_run(LATER)),
        check("the later ticket's qa never ran", not run.worker_runs("qa", LATER), run.stages_run(LATER)),
        check("the later ticket never reached Ready for QA", "Ready for QA" not in run.statuses_seen(LATER),
              run.statuses_seen(LATER)),
        check("the later ticket ends in Ready for Dev", run.status(LATER) == "Ready for Dev", run.status(LATER)),
        check("the later ticket is blocked by the first", FIRST in run.issue(LATER)["blockedBy"],
              run.issue(LATER)["blockedBy"]),
        check("the comment says the branches conflict and names the path",
              "branches conflict" in comments and "src/shared.txt" in comments, comments[:400]),
        check("the later ticket was never flagged needs attention", not run.ever_labelled(LATER, "needs attention")),
    ] + hygiene(run)
