import json
import os

from grading import check
from worker_grading import gates, judged, shipped

MUTATIONS = [
    ("a rename stops being held to the title rules (blank or over-long titles get through)",
     "src/reminders/routes.ts", "RENAME_WEAK_TITLE"),
    ("a rename reopens a done reminder", "src/reminders/store.ts", "RENAME_RESETS_STATUS"),
]


def grade(run):
    handback = run.handback()
    checks = shipped(run)
    gate_checks, skipped = gates(run, names=("typecheck", "lint", "test"))
    checks += gate_checks
    production = [path for path in run.changed_files()
                  if path.startswith("src/") and not path.endswith(".test.ts")]
    tests_changed = [path for path in run.changed_files() if path.endswith(".test.ts")]
    plan = run.read("workflows/%s/test-plan.md" % run.folder) or ""
    deleted = [line for line in run.diff("src").splitlines()
               if line.startswith("-") and not line.startswith("---") and ("it(" in line or "test(" in line)]
    checks += [
        check("route handed back is in_review", handback.get("route") == "in_review", handback.get("route")),
        check("test-plan.md was pushed", "## " in plan, run.changed_files()),
        check("qa added tests", bool(tests_changed), run.changed_files()),
        check("qa changed no production code", not production, production),
        check("qa removed none of dev's tests", not deleted, deleted[:3]),
    ]
    with open(os.path.join(os.path.dirname(run.case_dir), "_shared", "mutations.json")) as handle:
        patches = json.load(handle)
    for label, path, key in MUTATIONS:
        survived = mutant_survives(run, path, patches[key])
        checks.append(check("the suite goes red when " + label, survived is False,
                            "mutation target not found" if survived is None else "every test still passed"))
    tests = run.test_changes()
    with open(os.path.join(os.path.dirname(run.case_dir), "_shared", "tests-rubric.md")) as handle:
        rubric = handle.read()
    return checks + judged(run, "tests", rubric, tests)


def mutant_survives(run, path, patch):
    """Apply one text replacement to the pushed tree, run the suite, restore. None when it doesn't apply."""
    full = os.path.join(run.install(), path)
    with open(full) as handle:
        original = handle.read()
    if patch["find"] not in original:
        return None
    with open(full, "w") as handle:
        handle.write(original.replace(patch["find"], patch["replace"], 1))
    try:
        code, _ = run.sh(["npm", "run", "--silent", "test"])
    finally:
        with open(full, "w") as handle:
            handle.write(original)
    return code == 0
