from grading import check, hygiene

DEPENDENT, EPIC, SLICE = "ACM-310", "ACM-311", "ACM-312"


def grade(run):
    comments = "\n".join(run.comments(DEPENDENT))
    blockers = run.issue(DEPENDENT)["blockedBy"]
    return [
        check("the slice is merged into its epic branch",
              run.merged_into(run.issue(SLICE)["gitBranchName"], run.issue(EPIC)["gitBranchName"])),
        check("the dependent is blocked by the epic, not the slice", EPIC in blockers and SLICE not in blockers,
              blockers),
        check("cto never ran on the dependent", not run.worker_runs("cto", DEPENDENT), run.stages_run(DEPENDENT)),
        check("the comment names the epic and carries the slice",
              "relies on code only its branch adds" in comments and EPIC in comments and SLICE in comments,
              comments[:400]),
        check("the dependent was never flagged needs attention", not run.ever_labelled(DEPENDENT, "needs attention")),
    ] + hygiene(run)
