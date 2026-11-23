from grading import check, hygiene

OLDER, NEWER = "ACM-240", "ACM-241"


def grade(run):
    comments = "\n".join(run.comments(NEWER))
    return [
        check("the older ticket ends In Review", run.status(OLDER) == "In Review", run.status(OLDER)),
        check("the newer ticket is blocked by the older", OLDER in run.issue(NEWER)["blockedBy"],
              run.issue(NEWER)["blockedBy"]),
        check("the older ticket was not blocked by the newer", NEWER not in run.issue(OLDER)["blockedBy"],
              run.issue(OLDER)["blockedBy"]),
        check("the newer ticket's dev never ran", not run.worker_runs("dev", NEWER), run.stages_run(NEWER)),
        check("the newer ticket stays in Ready for Dev", run.statuses_seen(NEWER) == ["Ready for Dev"],
              run.statuses_seen(NEWER)),
        check("the comment names the blocker and the overlapping path",
              "footprints overlap" in comments and OLDER in comments and "src/reminders" in comments,
              comments[:400]),
        check("the newer ticket was never flagged needs attention", not run.ever_labelled(NEWER, "needs attention")),
    ] + hygiene(run)
