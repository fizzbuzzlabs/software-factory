#!/usr/bin/env python3
"""What a fake pipeline worker runs: `bash .dev/worker.sh <stage> <TICKET-ID>`.

Plays one scripted stage for one ticket: re-homes the worktree onto the ticket branch, waits,
writes and pushes the scripted files, and prints the scripted hand-back as one JSON line.
Each start and end is logged so graders can see who ran, when, and how many overlapped.
"""

import fcntl
import json
import os
import subprocess
import sys
import time

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(RUN_DIR, "state")


def git(*arguments):
    return subprocess.run(["git"] + list(arguments), capture_output=True, text=True)


def log(entry):
    entry["epoch"] = time.time()
    with open(os.path.join(STATE, "workers.jsonl"), "a") as handle:
        handle.write(json.dumps(entry) + "\n")


def next_index(key):
    path = os.path.join(STATE, "worker-counts.json")
    with open(path + ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        counts = {}
        if os.path.exists(path):
            with open(path) as handle:
                counts = json.load(handle)
        index = counts.get(key, 0)
        counts[key] = index + 1
        with open(path, "w") as handle:
            json.dump(counts, handle)
        return index


def reveal(keys):
    """Put seeded-but-hidden tickets on the fake board, as if someone filed them mid-run."""
    path = os.path.join(STATE, "linear.json")
    with open(path + ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with open(path) as handle:
            linear = json.load(handle)
        with open(os.path.join(STATE, "hidden.json")) as handle:
            hidden = json.load(handle)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        for key in keys:
            issue = hidden.get(key)
            if issue is None or key in linear["issues"]:
                continue
            issue["createdAt"] = issue["updatedAt"] = stamp
            linear["issues"][key] = issue
            linear["history"].append({"at": stamp, "issue": key, "status": issue["status"],
                                      "labels": list(issue["labels"])})
        temporary = path + ".tmp"
        with open(temporary, "w") as handle:
            json.dump(linear, handle, indent=1)
        os.replace(temporary, path)
    log({"event": "reveal", "tickets": list(keys)})


def finish(stage, ticket, index, handback):
    log({"event": "end", "stage": stage, "ticket": ticket, "index": index, "pid": os.getpid(),
         "status": handback.get("status")})
    print(json.dumps(handback))


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "summary": "usage: worker.sh <stage> <TICKET-ID>"}))
        return
    stage, ticket = sys.argv[1].lower(), sys.argv[2].upper()
    with open(os.path.join(RUN_DIR, "scenario.json")) as handle:
        scenario = json.load(handle)
    info = scenario["tickets"].get(ticket)
    scripts = scenario["workers"].get(ticket, {}).get(stage)
    if info is None or not scripts:
        print(json.dumps({"status": "error", "summary": "no %s work is defined for %s" % (stage, ticket)}))
        return

    index = next_index(ticket + ":" + stage)
    script = scripts[min(index, len(scripts) - 1)]
    cwd = os.getcwd()
    log({"event": "start", "stage": stage, "ticket": ticket, "index": index, "pid": os.getpid(), "cwd": cwd})

    branch = info["branch"]
    git("fetch", "origin")
    on_origin = git("rev-parse", "--verify", "--quiet", "refs/remotes/origin/" + branch).returncode == 0
    base = "origin/" + branch if on_origin else info["lane_base"]
    switched = git("switch", "--no-track", "-C", branch, base)
    if switched.returncode != 0:
        finish(stage, ticket, index, {
            "status": "error", "produced": "none", "worktree": cwd,
            "summary": "could not re-home onto %s: %s" % (branch, switched.stderr.strip())})
        return

    if script.get("merges_lane_base"):
        merged = git("merge", "--no-edit", "-X", "ours", info["lane_base"])
        if merged.returncode != 0:
            git("merge", "--abort")
            finish(stage, ticket, index, {
                "status": "blocked", "produced": "none", "worktree": cwd,
                "summary": "could not merge %s: %s" % (info["lane_base"], merged.stderr.strip())})
            return

    if script.get("reveals"):
        reveal(script["reveals"])

    time.sleep(script.get("delay", scenario.get("delay", 3)))

    if script.get("crash"):
        log({"event": "end", "stage": stage, "ticket": ticket, "index": index, "pid": os.getpid(),
             "status": "crash"})
        sys.stderr.write("Killed: 9\n")
        sys.exit(137)

    produced = "none"
    writes = script.get("writes") or {}
    if writes:
        for path, content in writes.items():
            path = path.replace("{folder}", info["folder"])
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "w") as handle:
                handle.write(content.replace("{index}", str(index)))
        git("add", "-A")
        git("commit", "-m", "%s %s: round %d" % (ticket, stage, index + 1))
        sha = git("rev-parse", "HEAD").stdout.strip()
        if not script.get("no_push"):
            pushed = git("push", "origin", "HEAD:refs/heads/" + branch)
            if pushed.returncode != 0:
                finish(stage, ticket, index, {
                    "status": "error", "produced": "none", "worktree": cwd,
                    "summary": "push rejected: " + pushed.stderr.strip()})
                return
        produced = "%s@%s" % (branch, sha)

    handback = {"status": script.get("status", "done"),
                "summary": script.get("summary", "").replace("{folder}", info["folder"]),
                "produced": produced, "worktree": cwd}
    handback.update(script.get("extra") or {})
    finish(stage, ticket, index, handback)


if __name__ == "__main__":
    main()
