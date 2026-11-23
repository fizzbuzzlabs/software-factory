import re

from grading import check, hygiene, untouched


def grade(run):
    report = run.final_message()
    waiting = re.search(r"ACM-31[^\n]*ACM-30", report) is not None
    return [
        check("ACM-30 ends In Review", run.status("ACM-30") == "In Review", run.status("ACM-30")),
        check("ACM-30 is in the review pool", run.merged_into(run.issue("ACM-30")["gitBranchName"], "review-pool")),
        check("the report says ACM-31 waits on ACM-30", waiting, report[-900:]),
        check("ACM-32 keeps its needs attention label", "needs attention" in run.labels("ACM-32"),
              run.labels("ACM-32")),
        check("ACM-31 was not flagged", "needs attention" not in run.labels("ACM-31"), run.labels("ACM-31")),
    ] + untouched(run, "ACM-31", "Ready for Dev") + untouched(run, "ACM-32", "Ready for Dev") + hygiene(run)
