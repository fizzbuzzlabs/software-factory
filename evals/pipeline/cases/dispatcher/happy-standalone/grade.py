from grading import check, hygiene

TICKET = "ACM-1"
STAGES = ["architect", "cto", "dev", "qa"]
PATH = ["Spec Done", "Contract Review", "Ready for Dev", "Ready for QA", "In Review"]


def grade(run):
    branch = run.issue(TICKET)["gitBranchName"]
    pool = run.pulls(head="review-pool", base="main", state="open")
    review_tickets = [issue for issue in run.issues_labelled("review-pool") if issue["id"] != TICKET]
    return [
        check("ticket ends In Review", run.status(TICKET) == "In Review", run.status(TICKET)),
        check("ticket passed through every stage's status in order", run.statuses_seen(TICKET) == PATH,
              run.statuses_seen(TICKET)),
        check("each stage ran once, in order", run.stages_run(TICKET) == STAGES, run.stages_run(TICKET)),
        check("no lifecycle label left on the ticket",
              not {"in progress", "needs attention"} & set(run.labels(TICKET)), run.labels(TICKET)),
        check("ticket was claimed while a worker ran", run.ever_labelled(TICKET, "in progress")),
        check("ticket branch is in the review pool", run.merged_into(branch, "review-pool"),
              run.origin_branches()),
        check("one open pool PR into main, ready for review",
              len(pool) == 1 and not pool[0]["draft"], [(p["head"], p["base"], p["draft"]) for p in run.pulls()]),
        check("pool PR body fixes the ticket", bool(pool) and ("Fixes " + TICKET) in pool[0]["body"],
              pool[0]["body"][:300] if pool else ""),
        check("a review ticket exists, In Review", len(review_tickets) == 1
              and review_tickets[0]["status"] == "In Review", [t["id"] for t in review_tickets]),
        check("pool was verified", any(entry["verdict"] == "PASS" for entry in run.verify_log), run.verify_log),
    ] + hygiene(run)
