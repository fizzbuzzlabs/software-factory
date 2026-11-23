#!/usr/bin/env python3
"""Grade a kept run again, after changing a grader.

    regrade.py <case> <run dir>                         a dispatcher case
    regrade.py --suite worker <case> <run dir>          a worker case
    regrade.py ... --write results/<label>/.../summary.json   also replace that summary's checks
"""

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))

import e2e_grading
import grading
import worker_grading


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case")
    parser.add_argument("run_dir")
    parser.add_argument("--suite", default="dispatcher", choices=["dispatcher", "worker", "e2e"])
    parser.add_argument("--write", metavar="SUMMARY")
    options = parser.parse_args()
    case_dir = os.path.join(HERE, "cases", options.suite, options.case)
    if options.suite == "e2e":
        checks, numbers = e2e_grading.grade(options.run_dir, case_dir)
        report(checks, options, {"numbers": numbers})
        return
    spec = importlib.util.spec_from_file_location("case_grade", os.path.join(case_dir, "grade.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = grading.Run(options.run_dir) if options.suite == "dispatcher" \
        else worker_grading.WorkerRun(options.run_dir, case_dir)
    report(module.grade(run), options, {})


def report(checks, options, extra):
    for entry in checks:
        print("%s %s%s" % ("ok  " if entry["ok"] else "FAIL", entry["name"],
                           "" if entry["ok"] else "  <- " + entry["detail"][:400]))
    passed = all(entry["ok"] for entry in checks)
    if options.write:
        with open(options.write) as handle:
            summary = json.load(handle)
        summary.update({"checks": checks, "passed": passed, "regraded": True})
        summary.update(extra)
        summary.pop("void", None)
        with open(options.write, "w") as handle:
            json.dump(summary, handle, indent=1)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
