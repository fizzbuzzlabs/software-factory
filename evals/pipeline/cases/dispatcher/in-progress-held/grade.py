from grading import check, hygiene

HELD, FREE = "ACM-200", "ACM-201"


def grade(run):
    report = run.final_message()
    section = report.split("In progress elsewhere", 1)[1][:400] if "In progress elsewhere" in report else ""
    return [
        check("the free ticket ends In Review", run.status(FREE) == "In Review", run.status(FREE)),
        check("the held ticket had no worker", not run.stages_run(HELD), run.stages_run(HELD)),
        check("the held ticket stays in Ready for Dev", run.statuses_seen(HELD) == ["Ready for Dev"],
              run.statuses_seen(HELD)),
        check("nothing was pushed to the held ticket's branch",
              not run.pushes_to(run.issue(HELD)["gitBranchName"])),
        check("the held ticket keeps its in progress label", "in progress" in run.labels(HELD), run.labels(HELD)),
        check("the held ticket was never flagged needs attention", not run.ever_labelled(HELD, "needs attention")),
        check("the report's In progress elsewhere section names the held ticket", HELD in section, report[-600:]),
    ] + hygiene(run)
