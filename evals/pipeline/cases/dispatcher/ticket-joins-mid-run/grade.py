from grading import check, hygiene

FIRST, LATE = "ACM-210", "ACM-211"


def grade(run):
    late = run.linear["issues"].get(LATE, {}).get("status")
    filed = run.revealed_at(LATE)
    late_dev = run.worker_runs("dev", LATE)
    return [
        check("the late ticket was filed while the first dev worker was out", filed is not None, filed),
        check("the same run picked up the late ticket", bool(late_dev) and late_dev[0]["start"] >= (filed or 0),
              run.stages_run(LATE)),
        check("the late ticket ends In Review", late == "In Review", late),
        check("the first ticket ends In Review", run.status(FIRST) == "In Review", run.status(FIRST)),
    ] + hygiene(run)
