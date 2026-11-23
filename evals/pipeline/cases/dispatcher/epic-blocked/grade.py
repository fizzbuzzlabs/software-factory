from grading import check, hygiene

EPIC, SLICE, FREE = "ACM-260", "ACM-261", "ACM-268"


def grade(run):
    return [
        check("the unrelated ticket ends In Review", run.status(FREE) == "In Review", run.status(FREE)),
        check("the slice of the blocked epic had no worker", not run.stages_run(SLICE), run.stages_run(SLICE)),
        check("the slice stays in Ready for Dev", run.statuses_seen(SLICE) == ["Ready for Dev"],
              run.statuses_seen(SLICE)),
        check("the slice was never claimed", not run.ever_labelled(SLICE, "in progress")),
        check("the slice was never flagged needs attention", not run.ever_labelled(SLICE, "needs attention")),
        check("the epic was never flagged needs attention", not run.ever_labelled(EPIC, "needs attention")),
    ] + hygiene(run)
