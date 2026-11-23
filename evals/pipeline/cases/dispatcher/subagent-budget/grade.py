from grading import check, halted, hygiene

TICKETS = ["ACM-%d" % number for number in range(101, 109)]


def grade(run):
    most = run.max_overlap("architect")
    ran = sorted(entry["ticket"] for entry in run.worker_runs("architect"))
    checks = [
        check("never more than 5 architects in flight (cap 20, an architect holds 4)", most <= 5, most),
        check("architects did run in parallel", most >= 3, most),
        check("every ticket's architect ran exactly once", ran == TICKETS, ran),
    ]
    for key in TICKETS:
        checks += halted(run, key, "Spec Done")
    return checks + hygiene(run)
