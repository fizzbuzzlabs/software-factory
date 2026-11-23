from grading import check, halted, hygiene

TICKET = "ACM-130"


def grade(run):
    runs = run.worker_runs("dev", TICKET)
    return [
        check("dev was not retried in a loop (at most 2 runs)", 1 <= len(runs) <= 2, len(runs)),
        check("qa never ran", not run.worker_runs("qa", TICKET)),
    ] + halted(run, TICKET, "Ready for Dev") + hygiene(run)
