#!/usr/bin/env python3
"""Dry-run every worker case without a model: build its world and run the app's gates on the seeded branch.

    check_cases.py [case-glob]

A seed is sound when the ticket branch passes typecheck, lint and debt:check, and its tests pass
(cases that plant a defect still pass their own tests; the defect is what QA is there to find).
"""

import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))

import worker_scaffold


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "*"
    cases = os.path.join(HERE, "cases", "worker")
    failed = False
    for case in sorted(os.listdir(cases)):
        if not fnmatch.fnmatch(case, pattern) or not os.path.exists(os.path.join(cases, case, "case.json")):
            continue
        run_dir = tempfile.mkdtemp(prefix="case-" + case + "-")
        try:
            world = worker_scaffold.scaffold_worker(os.path.join(cases, case), run_dir, os.path.join(HERE, "fakes"),
                                                    os.path.join(HERE, ".arms", "main", "real-workers"))
            os.symlink(os.path.join(HERE, "sample-app", "node_modules"), os.path.join(world["tree"], "node_modules"))
            results = []
            for gate in ("typecheck", "lint", "test", "debt:check"):
                done = subprocess.run(["npm", "run", "--silent", gate], cwd=world["tree"], capture_output=True, text=True)
                results.append("%s %s" % (gate, "ok" if done.returncode == 0 else "FAIL"))
                if done.returncode != 0:
                    failed = True
                    print((done.stdout + done.stderr)[-800:])
            files = subprocess.run(["git", "ls-files", "workflows"], cwd=world["tree"], capture_output=True, text=True)
            print("%-22s %s | %s" % (case, ", ".join(results), " ".join(os.path.basename(f) for f in files.stdout.split())))
        except Exception as error:
            failed = True
            print("%-22s ERROR %r" % (case, error))
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
