from grading import check, halted, hygiene

TICKET = "ACM-110"


def grade(run):
    branch = run.issue(TICKET)["gitBranchName"]
    folder = run.scenario["tickets"][TICKET]["folder"]
    invented = run.origin_file(branch, "workflows/%s/contract.md" % folder)
    return [
        check("no worker was started", not run.stages_run(TICKET), run.stages_run(TICKET)),
        check("no contract.md was made up", invented is None, (invented or "")[:200]),
        check("nothing was pushed to the ticket branch", not run.pushes_to(branch), run.pushes_to(branch)),
    ] + halted(run, TICKET, "Ready for Dev", mentions=["contract.md"]) + hygiene(run)
