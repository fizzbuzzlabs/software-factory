import re
import subprocess

from grading import check
from worker_grading import gates, replay_commits, shipped


def text_at(run, sha, pattern):
    """Paths under src/ whose content matches a pattern at one commit."""
    found = subprocess.run(["git", "grep", "-lE", pattern, sha, "--", "src"], cwd=run.checkout(),
                           capture_output=True, text=True)
    return [line.split(":", 1)[1] for line in found.stdout.splitlines()]


def grade(run):
    handback = run.handback()
    checks = shipped(run)
    gate_checks, skipped = gates(run)
    checks += gate_checks
    passed, failures, _ = run.replay("past.json")
    commits = run.commits()
    subjects = [commit["subject"] for commit in commits]
    tidy = [index for index, subject in enumerate(subjects) if re.search(r"\btidy:", subject)]
    behavior = [index for index, subject in enumerate(subjects) if re.search(r"behavior \d+", subject, re.I)]
    tidy_first = bool(tidy) and bool(behavior) and tidy[0] < behavior[0]
    tidy_sha = commits[tidy[0]]["sha"] if tidy else None
    renamed_in_tidy = bool(tidy_sha) and not text_at(run, tidy_sha, r"\bcheckBody\b")
    rule_in_tidy = text_at(run, tidy_sha, "due_in_past") if tidy_sha else []
    _, tidy_broken = replay_commits(run, pattern=r"\btidy:")
    claimed, broken = replay_commits(run)
    leftovers = sorted(path for path, text in run.source(tests=True).items() if re.search(r"\bcheckBody\b", text))
    old_file = run.read("src/reminders/body.ts")
    return checks + [
        check("hidden requests pass against the running app", passed, failures[:4]),
        check("a `tidy:` commit comes before the first behavior commit", tidy_first, subjects),
        check("the rename is complete in the tidy commit", renamed_in_tidy, subjects),
        check("the tidy commit carries no new behavior", bool(tidy_sha) and not rule_in_tidy, rule_in_tidy),
        check("the tidy commit is green on its own", bool(tidy) and not tidy_broken, tidy_broken[:2]),
        check("every behavior commit is green on its own", bool(claimed) and not broken, broken[:2]),
        check("the old names are gone: no alias or re-export", not leftovers and old_file is None, leftovers),
        check("verify verdict handed back is PASS", handback.get("verify") == "PASS", handback.get("verify")),
        check("no test was skipped or left todo", not skipped, skipped[:3]),
    ]
