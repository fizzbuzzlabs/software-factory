from grading import check, hygiene

TICKET = "ACM-55"


def grade(run):
    branch = run.issue(TICKET)["gitBranchName"]
    with open(run.dir + "/state/branch-tip-before.txt") as handle:
        before = handle.read().strip()
    kept_history = run.origin_git("merge-base", "--is-ancestor", before, "refs/heads/" + branch)[0] == 0
    return [
        check("ticket branch now contains main", run.merged_into("main", branch)),
        check("the branch's earlier commits are still in its history (merged, not rebased)", kept_history),
        check("qa ran once", run.stages_run(TICKET) == ["qa"], run.stages_run(TICKET)),
        check("ticket ends In Review", run.status(TICKET) == "In Review", run.status(TICKET)),
    ] + hygiene(run)
