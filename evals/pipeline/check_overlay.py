#!/usr/bin/env python3
"""Check that the sample app with code overlays laid over it still passes its own gates.

    check_overlay.py rename                       sample app + _shared/code/rename
    check_overlay.py rename rename-defect         overlays applied in order
    check_overlay.py body-module --delete src/reminders/reminder.test.ts
    check_overlay.py snooze --replay cases/worker/_shared/snooze-hidden.json
    check_overlay.py rename --mutate RENAME_WEAK_TITLE     gates with one mutation from mutations.json applied

Prints each gate's result, and for --replay each failed hidden request. Exits 1 if a gate fails.
"""

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))

import worker_grading
import worker_scaffold

GATES = ["typecheck", "lint", "test", "debt:check"]


@contextlib.contextmanager
def booted(tree):
    process = subprocess.Popen(["npm", "run", "--silent", "start"], cwd=tree, env=dict(os.environ, PORT="0"),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    url, deadline = None, time.time() + 40
    try:
        while time.time() < deadline:
            line = process.stdout.readline()
            match = re.search(r'"port"\s*:\s*(\d+)', line or "")
            if match:
                url = "http://127.0.0.1:" + match.group(1)
                break
            if not line and process.poll() is not None:
                break
        yield url
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, 15)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("overlays", nargs="*")
    parser.add_argument("--delete", action="append", default=[])
    parser.add_argument("--replay", action="append", default=[])
    parser.add_argument("--mutate", action="append", default=[], help="KEY=path: apply mutations.json[KEY] to path")
    parser.add_argument("--keep", action="store_true")
    options = parser.parse_args()

    tree = tempfile.mkdtemp(prefix="overlay-")
    os.rmdir(tree)
    app = os.path.join(HERE, "sample-app")
    shutil.copytree(app, tree, ignore=shutil.ignore_patterns("node_modules", "reports"))
    os.symlink(os.path.join(app, "node_modules"), os.path.join(tree, "node_modules"))
    for name in options.overlays:
        source = os.path.join(HERE, "cases", "worker", "_shared", "code", name)
        if not os.path.isdir(source):
            sys.exit("no overlay at " + source)
        worker_scaffold.overlay(source, tree)
    for path in options.delete:
        os.remove(os.path.join(tree, path))
    with open(os.path.join(HERE, "cases", "worker", "_shared", "mutations.json")) as handle:
        mutations = json.load(handle) if options.mutate else {}
    for entry in options.mutate:
        key, path = entry.split("=", 1)
        with open(os.path.join(tree, path)) as handle:
            text = handle.read()
        if text.count(mutations[key]["find"]) != 1:
            sys.exit("%s: `find` occurs %d times in %s, expected exactly 1" % (key, text.count(mutations[key]["find"]), path))
        with open(os.path.join(tree, path), "w") as handle:
            handle.write(text.replace(mutations[key]["find"], mutations[key]["replace"]))

    failed = False
    for gate in GATES:
        done = subprocess.run(["npm", "run", "--silent", gate], cwd=tree, capture_output=True, text=True)
        print("%-11s %s" % (gate, "ok" if done.returncode == 0 else "FAIL"))
        if done.returncode != 0:
            failed = True
            print((done.stdout + done.stderr)[-1500:])
    for script in options.replay:
        with open(script) as handle:
            steps = json.load(handle)
        with booted(tree) as url:
            failures, _ = worker_grading.run_steps(url, steps) if url else (["the service did not boot"], [])
        print("replay %s: %s" % (os.path.basename(script), "ok" if not failures else "%d failed" % len(failures)))
        for failure in failures:
            print("   - " + failure)
    print("tree: " + tree if options.keep else "")
    if not options.keep:
        shutil.rmtree(tree, ignore_errors=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
