from grading import check, halted, hygiene

TICKET = "ACM-65"


def grade(run):
    runs = run.worker_runs("dev", TICKET)
    gaps = [later["start"] - (earlier["end"] or later["start"]) for earlier, later in zip(runs, runs[1:])]
    return [
        check("dev ran 3 times: two retries, then the halt", len(runs) == 3, len(runs)),
        check("each retry waited for the port (4+ minutes)", len(gaps) == 2 and min(gaps) >= 240, gaps),
        check("qa never ran", not run.worker_runs("qa", TICKET)),
    ] + halted(run, TICKET, "Ready for Dev", mentions=["blocked", "port"]) + hygiene(run)
