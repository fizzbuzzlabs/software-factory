from grading import check, hygiene

TICKET = "ACM-45"


def grade(run):
    done = [entry for entry in run.worker_runs("dev", TICKET) if entry["status"] == "done"]
    return [
        check("the ticket was not left for a human: a clean leftover tree is no reason to stop",
              "needs attention" not in run.labels(TICKET), run.labels(TICKET)),
        check("dev did its work on the ticket", len(done) == 1, run.worker_runs(ticket=TICKET)),
        check("ticket ends In Review", run.status(TICKET) == "In Review", run.status(TICKET)),
    ] + hygiene(run)
