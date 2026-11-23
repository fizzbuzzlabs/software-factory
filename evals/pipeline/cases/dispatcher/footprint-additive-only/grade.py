from grading import check, hygiene

TICKETS = ["ACM-245", "ACM-246"]


def grade(run):
    checks = []
    for key in TICKETS:
        checks += [
            check("%s ends In Review" % key, run.status(key) == "In Review", run.status(key)),
            check("%s got no blocked-by" % key, not run.issue(key)["blockedBy"], run.issue(key)["blockedBy"]),
            check("%s got no overlap comment" % key,
                  not any("Blocked by" in body for body in run.comments(key)), run.comments(key)),
        ]
    return checks + hygiene(run)
