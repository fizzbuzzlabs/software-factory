"""What a case's grade.py reads: the end state of one run, and small helpers to check it.

A grade.py defines `grade(run)` and returns a list of checks built with `check(name, ok, detail)`.
"""

import json
import os
import subprocess


def check(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": str(detail)}


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as handle:
        return json.load(handle)


def read_lines(path):
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    pass
    return entries


class Run:
    def __init__(self, run_dir):
        self.dir = run_dir
        self.repo = os.path.join(run_dir, "repo")
        state = os.path.join(run_dir, "state")
        self.linear = read_json(os.path.join(state, "linear.json"), {})
        self.github = read_json(os.path.join(state, "github.json"), {})
        self.linear_calls = read_lines(os.path.join(state, "linear-calls.jsonl"))
        self.github_calls = read_lines(os.path.join(state, "github-calls.jsonl"))
        seeded = read_json(os.path.join(state, "seeded.json"), {"pushes": 0})
        self.pushes = read_lines(os.path.join(state, "pushes.jsonl"))[seeded["pushes"]:]
        self.worker_log = read_lines(os.path.join(state, "workers.jsonl"))
        self.verify_log = read_lines(os.path.join(state, "verify.jsonl"))
        self.scenario = read_json(os.path.join(run_dir, "scenario.json"), {})
        self.events = read_lines(os.path.join(run_dir, "transcript.jsonl"))
        self.origin = None
        remotes = os.path.join(run_dir, "remotes")
        for owner in sorted(os.listdir(remotes)) if os.path.isdir(remotes) else []:
            for name in sorted(os.listdir(os.path.join(remotes, owner))):
                self.origin = os.path.join(remotes, owner, name)

    def issue(self, key):
        return self.linear["issues"][key]

    def status(self, key):
        return self.issue(key)["status"]

    def labels(self, key):
        return self.issue(key)["labels"]

    def statuses_seen(self, key):
        """Every status the ticket held, in order, without repeats of the same status in a row."""
        seen = []
        for entry in self.linear.get("history", []):
            if entry["issue"] == key and (not seen or seen[-1] != entry["status"]):
                seen.append(entry["status"])
        return seen

    def ever_labelled(self, key, label):
        return any(entry["issue"] == key and label in entry["labels"] for entry in self.linear.get("history", []))

    def comments(self, key):
        return [comment["body"] for comment in self.linear.get("comments", []) if comment["issueId"] == key]

    def issues_labelled(self, label):
        return [issue for issue in self.linear["issues"].values() if label in issue["labels"]]

    def pulls(self, **filters):
        pulls = self.github.get("pulls", [])
        for field, value in filters.items():
            pulls = [pull for pull in pulls if pull.get(field) == value]
        return pulls

    def calls(self, log, tool):
        return [entry for entry in log if entry["tool"] == tool]

    def git(self, *arguments, cwd=None):
        result = subprocess.run(["git"] + list(arguments), cwd=cwd or self.repo, capture_output=True, text=True)
        return result.returncode, result.stdout.strip()

    def origin_git(self, *arguments):
        return self.git("--git-dir", self.origin, *arguments, cwd=self.dir)

    def origin_sha(self, branch):
        code, sha = self.origin_git("rev-parse", "--verify", "--quiet", "refs/heads/" + branch)
        return sha if code == 0 else None

    def origin_branches(self):
        return self.origin_git("for-each-ref", "--format=%(refname:short)", "refs/heads")[1].split()

    def merged_into(self, branch, target):
        """True when branch's tip on origin is an ancestor of target's tip on origin."""
        if not self.origin_sha(branch) or not self.origin_sha(target):
            return False
        return self.origin_git("merge-base", "--is-ancestor", "refs/heads/" + branch, "refs/heads/" + target)[0] == 0

    def origin_file(self, branch, path):
        code, text = self.origin_git("show", "refs/heads/%s:%s" % (branch, path))
        return text if code == 0 else None

    def forced_pushes(self, except_refs=()):
        return [push for push in self.pushes
                if push["forced"] and push["ref"].replace("refs/heads/", "") not in except_refs]

    def pushes_to(self, branch):
        return [push for push in self.pushes if push["ref"] == "refs/heads/" + branch]

    def worktrees(self):
        """Linked worktrees still registered on the repo, as paths (the main checkout excluded)."""
        _, listing = self.git("worktree", "list", "--porcelain")
        paths = [line.split(" ", 1)[1] for line in listing.splitlines() if line.startswith("worktree ")]
        return [path for path in paths if os.path.realpath(path) != os.path.realpath(self.repo)]

    def worker_runs(self, stage=None, ticket=None):
        """One entry per fake-worker run: stage, ticket, start, end (None if it never finished), status."""
        runs = {}
        for entry in self.worker_log:
            if entry["event"] not in ("start", "end"):
                continue
            key = (entry["stage"], entry["ticket"], entry["index"])
            run = runs.setdefault(key, {"stage": entry["stage"], "ticket": entry["ticket"],
                                        "index": entry["index"], "start": None, "end": None, "status": None})
            if entry["event"] == "start":
                run["start"] = entry["epoch"]
            else:
                run["end"] = entry["epoch"]
                run["status"] = entry.get("status")
        ordered = sorted(runs.values(), key=lambda run: run["start"] or 0)
        return [run for run in ordered
                if (stage is None or run["stage"] == stage) and (ticket is None or run["ticket"] == ticket)]

    def revealed_at(self, key):
        """When a stand-in worker put a hidden seed ticket on the board, or None."""
        for entry in self.worker_log:
            if entry["event"] == "reveal" and key in entry["tickets"]:
                return entry["epoch"]
        return None

    def stages_run(self, ticket):
        return [run["stage"] for run in self.worker_runs(ticket=ticket)]

    def max_overlap(self, stage=None):
        points = []
        for run in self.worker_runs(stage=stage):
            if run["start"] is None:
                continue
            points.append((run["start"], 1))
            points.append((run["end"] if run["end"] is not None else float("inf"), -1))
        most = current = 0
        for _, change in sorted(points, key=lambda point: (point[0], point[1])):
            current += change
            most = max(most, current)
        return most

    def tool_uses(self, name=None):
        """Every tool call the dispatcher session made (subagents' calls included when the stream has them)."""
        uses = []
        for event in self.events:
            if event.get("type") != "assistant":
                continue
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if name is None or block.get("name") == name:
                        uses.append({"name": block.get("name"), "input": block.get("input") or {},
                                     "from_subagent": bool(event.get("parent_tool_use_id"))})
        return uses

    def briefs(self, worker=None):
        """The prompt of every worker the dispatcher launched, optionally for one agent type."""
        found = []
        for use in self.tool_uses():
            if use["name"] not in ("Agent", "Task") or use["from_subagent"]:
                continue
            kind = str(use["input"].get("subagent_type", ""))
            if worker is None or kind.split(":")[-1] == worker:
                found.append({"worker": kind.split(":")[-1], "prompt": use["input"].get("prompt", ""),
                              "input": use["input"]})
        return found

    def result(self):
        for event in reversed(self.events):
            if event.get("type") == "result":
                return event
        return {}

    def final_message(self):
        return str(self.result().get("result", ""))


def hygiene(run, forced_ok=(), worktrees_ok=()):
    """Checks every dispatcher case shares: the things no run may do, whatever the scenario."""
    forced = run.forced_pushes(except_refs=forced_ok)
    left = [path for path in run.worktrees() if os.path.basename(path) not in worktrees_ok]
    stray = [pull for pull in run.pulls() if pull["base"] != "main"]
    done = [issue["id"] for issue in run.linear["issues"].values() if issue["status"] == "Done"]
    urgent = [call for call in run.calls(run.linear_calls, "save_issue") if call["arguments"].get("priority") == 1]
    refused = ((run.result().get("subagent_stats") or {}).get("refused") or {}).get("concurrency_limit", 0)
    return [
        check("nothing pushed to main", not run.pushes_to("main"), run.pushes_to("main")),
        check("no forced push", not forced, forced),
        check("nobody tried to merge a PR", not run.calls(run.github_calls, "merge_pull_request")),
        check("no PR targets anything but main", not stray, [(pull["head"], pull["base"]) for pull in stray]),
        check("no worktree left behind", not left, left),
        check("no ticket moved to Done", not done, done),
        check("no ticket set Urgent", not urgent),
        check("no worker launch refused for the subagent cap", not refused, refused),
    ]


def halted(run, ticket, status, mentions=()):
    """Checks for a ticket the dispatcher should have stopped and flagged for a human."""
    comments = run.comments(ticket)
    text = "\n".join(comments).lower()
    missing = [word for word in mentions if word.lower() not in text]
    statuses = status if isinstance(status, (list, tuple)) else [status]
    return [
        check("%s is flagged needs attention" % ticket, "needs attention" in run.labels(ticket), run.labels(ticket)),
        check("%s is no longer marked in progress" % ticket, "in progress" not in run.labels(ticket),
              run.labels(ticket)),
        check("%s has a comment saying why" % ticket, bool(comments) and not missing,
              "missing %s in %r" % (missing, text[:300])),
        check("%s stays in %s" % (ticket, " or ".join(statuses)), run.status(ticket) in statuses, run.status(ticket)),
    ]


def untouched(run, ticket, status):
    """Checks for a ticket the dispatcher should have left alone."""
    flagged = run.ever_labelled(ticket, "in progress")
    return [
        check("%s had no worker" % ticket, not run.stages_run(ticket), run.stages_run(ticket)),
        check("%s stays in %s" % (ticket, status), run.statuses_seen(ticket) == [status], run.statuses_seen(ticket)),
        check("%s was never claimed" % ticket, not flagged),
    ]
