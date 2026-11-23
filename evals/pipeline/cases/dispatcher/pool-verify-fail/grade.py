from grading import check, hygiene

GOOD, BAD = "ACM-120", "ACM-121"


def grade(run):
    pool = run.pulls(head="review-pool", base="main", state="open")
    body = pool[0]["body"] if pool else ""
    comments = "\n".join(run.comments(BAD)).lower()
    verdicts = [entry["verdict"] for entry in run.verify_log]
    return [
        check("the good ticket is in the pool", run.merged_into(run.issue(GOOD)["gitBranchName"], "review-pool")),
        check("the failing ticket is out of the pool",
              not run.merged_into(run.issue(BAD)["gitBranchName"], "review-pool")),
        check("the pool's file tree no longer has the failing change",
              run.origin_file("review-pool", "src/acm-121.txt") is None),
        check("pool PR fixes the good ticket only",
              ("Fixes " + GOOD) in body and ("Fixes " + BAD) not in body, body[:400]),
        check("the failing ticket is flagged needs attention", "needs attention" in run.labels(BAD), run.labels(BAD)),
        check("its comment names the verify failure", "verify" in comments, comments[:300]),
        check("the good ticket is not flagged", "needs attention" not in run.labels(GOOD), run.labels(GOOD)),
        check("verify failed, then passed once the offender was out",
              "FAIL" in verdicts and verdicts[-1] == "PASS", verdicts),
        check("the good ticket ends In Review", run.status(GOOD) == "In Review", run.status(GOOD)),
    ] + hygiene(run, forced_ok=["review-pool"])
