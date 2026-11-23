from grading import check, hygiene

BUILDING, BUILDING_SLICE, WAITING, WAITING_SLICE = "ACM-270", "ACM-271", "ACM-275", "ACM-276"


def grade(run):
    comments = "\n".join(run.comments(WAITING))
    return [
        check("the building epic's slice is merged into its epic branch",
              run.merged_into(run.issue(BUILDING_SLICE)["gitBranchName"], run.issue(BUILDING)["gitBranchName"])),
        check("the waiting epic is blocked by the building one", BUILDING in run.issue(WAITING)["blockedBy"],
              run.issue(WAITING)["blockedBy"]),
        check("the building epic is not blocked by the waiting one", WAITING not in run.issue(BUILDING)["blockedBy"],
              run.issue(BUILDING)["blockedBy"]),
        check("the waiting epic's slice never ran dev", not run.worker_runs("dev", WAITING_SLICE),
              run.stages_run(WAITING_SLICE)),
        check("the comment on the waiting epic names the blocker and the overlap",
              "footprints overlap" in comments and BUILDING in comments and "src/reminders" in comments,
              comments[:400]),
        check("nothing was flagged needs attention",
              not any(run.ever_labelled(key, "needs attention") for key in (WAITING, WAITING_SLICE))),
    ] + hygiene(run)
