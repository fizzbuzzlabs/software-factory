from grading import check, hygiene

EPIC, SLICE, STANDALONE = "ACM-280", "ACM-281", "ACM-285"


def grade(run):
    comments = "\n".join(run.comments(STANDALONE))
    blockers = run.issue(STANDALONE)["blockedBy"]
    return [
        check("the slice is merged into its epic branch",
              run.merged_into(run.issue(SLICE)["gitBranchName"], run.issue(EPIC)["gitBranchName"])),
        check("the standalone ticket is blocked by the epic, not the slice",
              EPIC in blockers and SLICE not in blockers, blockers),
        check("the standalone ticket's dev never ran", not run.worker_runs("dev", STANDALONE),
              run.stages_run(STANDALONE)),
        check("the standalone ticket stays in Ready for Dev", run.statuses_seen(STANDALONE) == ["Ready for Dev"],
              run.statuses_seen(STANDALONE)),
        check("the comment names the epic and the overlap",
              "footprints overlap" in comments and EPIC in comments and "src/reminders" in comments,
              comments[:400]),
        check("the standalone ticket was never flagged needs attention",
              not run.ever_labelled(STANDALONE, "needs attention")),
    ] + hygiene(run)
