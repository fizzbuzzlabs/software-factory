from grading import check, hygiene


def grade(run):
    retried = run.worker_runs("dev", "ACM-60")
    other = run.worker_runs("dev", "ACM-61")
    overlapped = bool(retried and other and other[0]["start"] < (retried[0]["end"] or 0) < (other[0]["end"] or 0))
    after = len(retried) == 2 and bool(other) and retried[1]["start"] >= (other[0]["end"] or float("inf"))
    checks = [
        check("the two dev workers ran at the same time", overlapped, [retried[:1], other[:1]]),
        check("ACM-60's dev ran twice", len(retried) == 2, len(retried)),
        check("the retry waited for the other dev worker to return", after, [retried, other]),
        check("ACM-60 was never flagged needs attention", not run.ever_labelled("ACM-60", "needs attention")),
        check("the port clash spent no round: one qa run each",
              len(run.worker_runs("qa", "ACM-60")) == 1 and len(run.worker_runs("qa", "ACM-61")) == 1,
              [run.stages_run("ACM-60"), run.stages_run("ACM-61")]),
    ]
    for key in ("ACM-60", "ACM-61"):
        checks.append(check("%s ends In Review" % key, run.status(key) == "In Review", run.status(key)))
    return checks + hygiene(run)
