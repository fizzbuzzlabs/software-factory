from grading import check, halted, hygiene

TICKET = "ACM-70"


def grade(run):
    return [
        check("qa ran twice, then the ticket halted", len(run.worker_runs("qa", TICKET)) == 2,
              run.stages_run(TICKET)),
        check("dev ran once, between the two qa runs", run.stages_run(TICKET) == ["qa", "dev", "qa"],
              run.stages_run(TICKET)),
        check("ticket never reached In Review", "In Review" not in run.statuses_seen(TICKET),
              run.statuses_seen(TICKET)),
    ] + halted(run, TICKET, ["Ready for QA", "Ready for Dev"], mentions=["DEF-1"]) + hygiene(run)
