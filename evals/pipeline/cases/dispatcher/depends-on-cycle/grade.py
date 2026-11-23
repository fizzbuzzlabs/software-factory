from grading import check, hygiene

DEPENDENT, OTHER = "ACM-320", "ACM-321"


def grade(run):
    comments = "\n".join(run.comments(DEPENDENT))
    return [
        check("the dependent moved to Contract Review and stopped there",
              run.statuses_seen(DEPENDENT) == ["Spec Done", "Contract Review"], run.statuses_seen(DEPENDENT)),
        check("no relation was added that would never clear", OTHER not in run.issue(DEPENDENT)["blockedBy"],
              run.issue(DEPENDENT)["blockedBy"]),
        check("the dependent is flagged needs attention", "needs attention" in run.labels(DEPENDENT),
              run.labels(DEPENDENT)),
        check("the comment says it can't wait on the other ticket",
              "Can't wait on" in comments and OTHER in comments, comments[:400]),
        check("cto never ran on the dependent", not run.worker_runs("cto", DEPENDENT), run.stages_run(DEPENDENT)),
    ] + hygiene(run)
