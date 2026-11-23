from grading import check, hygiene

DEPENDENT, BLOCKER = "ACM-300", "ACM-301"


def grade(run):
    comments = "\n".join(run.comments(DEPENDENT))
    return [
        check("the blocker ends In Review", run.status(BLOCKER) == "In Review", run.status(BLOCKER)),
        check("the dependent's contract moved it to Contract Review",
              run.statuses_seen(DEPENDENT) == ["Spec Done", "Contract Review"], run.statuses_seen(DEPENDENT)),
        check("the dependent is blocked by the ticket it relies on", BLOCKER in run.issue(DEPENDENT)["blockedBy"],
              run.issue(DEPENDENT)["blockedBy"]),
        check("the blocker is not blocked by the dependent", DEPENDENT not in run.issue(BLOCKER)["blockedBy"],
              run.issue(BLOCKER)["blockedBy"]),
        check("cto never ran on the dependent", not run.worker_runs("cto", DEPENDENT), run.stages_run(DEPENDENT)),
        check("the comment names the blocker and what is relied on",
              "relies on code only its branch adds" in comments and BLOCKER in comments and "snoozedUntil" in comments,
              comments[:400]),
        check("the dependent was never flagged needs attention", not run.ever_labelled(DEPENDENT, "needs attention")),
    ] + hygiene(run)
