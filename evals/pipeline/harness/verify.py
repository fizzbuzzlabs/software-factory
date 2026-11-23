#!/usr/bin/env python3
"""What the pretend app's `verify` skill runs: `bash .dev/verify.sh [<tree>]`.

Returns the case's scripted verdict for the tree it is pointed at. A rule fires when a named
file exists in that tree, so a verdict follows the content being verified: remove the
offending ticket's merge and the same tree passes.
"""

import json
import os
import sys
import time

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    tree = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    with open(os.path.join(RUN_DIR, "scenario.json")) as handle:
        rules = json.load(handle).get("verify") or {}
    verdict, reason = rules.get("default", "PASS"), rules.get("reason", "the app behaved as specified")
    for rule in rules.get("rules", []):
        if os.path.exists(os.path.join(tree, rule["if_present"])):
            verdict, reason = rule["verdict"], rule.get("reason", "")
            break
    with open(os.path.join(RUN_DIR, "state", "verify.jsonl"), "a") as handle:
        handle.write(json.dumps({"epoch": time.time(), "tree": tree, "verdict": verdict}) + "\n")
    print("VERDICT: %s — %s" % (verdict, reason))


if __name__ == "__main__":
    main()
