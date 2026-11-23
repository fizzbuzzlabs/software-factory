from grading import check, hygiene

EPIC, SLICES = "ACM-10", ["ACM-11", "ACM-12"]


def grade(run):
    epic_branch = run.issue(EPIC)["gitBranchName"]
    slice_branches = [run.issue(key)["gitBranchName"] for key in SLICES]
    into_epic = [pull for pull in run.pulls() if pull["base"] == epic_branch]
    slice_pulls = [pull for pull in run.pulls() if pull["head"] in slice_branches]
    epic_pulls = run.pulls(head=epic_branch, base="main", state="open")
    body = epic_pulls[0]["body"] if epic_pulls else ""
    review = [issue for issue in run.issues_labelled("review-pool")]
    checks = [
        check("no PR was opened into the epic branch", not into_epic, [(p["head"], p["base"]) for p in into_epic]),
        check("no slice got its own PR", not slice_pulls, [(p["head"], p["base"]) for p in slice_pulls]),
        check("one open epic PR into main, ready for review", len(epic_pulls) == 1 and not epic_pulls[0]["draft"],
              [(p["head"], p["base"], p["draft"]) for p in run.pulls()]),
        check("epic PR body fixes every slice", all(("Fixes " + key) in body for key in SLICES), body[:400]),
        check("epic ticket ends In Review", run.status(EPIC) == "In Review", run.status(EPIC)),
        check("epic branch was verified", any(entry["verdict"] == "PASS" for entry in run.verify_log), run.verify_log),
        check("the epic has a review ticket", len(review) == 1 and EPIC in review[0]["title"],
              [issue["title"] for issue in review]),
        check("the epic itself was never built", not run.stages_run(EPIC), run.stages_run(EPIC)),
    ]
    if review:
        ticket = review[0]
        related = [key for key in SLICES
                   if key in ticket["relatedTo"] or ticket["id"] in run.issue(key)["relatedTo"]]
        checks.append(check("the review ticket is related to every slice", related == SLICES, ticket["relatedTo"]))
    for key, branch in zip(SLICES, slice_branches):
        checks += [
            check("%s ends In Review" % key, run.status(key) == "In Review", run.status(key)),
            check("%s ran qa only" % key, run.stages_run(key) == ["qa"], run.stages_run(key)),
            check("%s is merged into the epic branch" % key, run.merged_into(branch, epic_branch)),
            check("%s carries no lifecycle label" % key,
                  not {"in progress", "needs attention"} & set(run.labels(key)), run.labels(key)),
        ]
    return checks + hygiene(run)
