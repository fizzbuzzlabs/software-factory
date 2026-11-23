"""Build one run's world from a dispatcher case: a pretend app repo, its origin, and the fake boards.

A run directory holds:
  repo/                           the pretend app repo the dispatcher runs in
  remotes/acme-labs/sample-app.git its origin (a local bare repo that logs every push)
  state/                          fake Linear and GitHub state, call logs, worker and verify logs
  harness/                        worker.py and verify.py, called by the repo's .dev/*.sh
  scenario.json                   what each fake worker and the verify stub will do
  mcp.json                        the two fake MCP servers
"""

import importlib.util
import json
import os
import shutil
import stat
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OWNER, REPO = "acme-labs", "sample-app"
TEAM = {"id": "team-acme", "name": "Acme", "key": "ACM"}

STATUSES = [
    ("Triage", "triage"), ("Backlog", "backlog"), ("Todo", "unstarted"), ("Spec Done", "started"),
    ("Contract Review", "started"), ("Ready for Dev", "started"), ("Ready for QA", "started"),
    ("In Review", "started"), ("Done", "completed"), ("Canceled", "canceled"), ("Duplicate", "duplicate"),
]
LABELS = ["in progress", "needs attention", "review-pool", "systems-engineer", "bug"]
PROJECTS = ["App", "Factory"]
STAGES = ["architect", "cto", "dev", "qa"]
ARTIFACTS_BY_STATUS = {
    "Spec Done": ["spec.md"],
    "Contract Review": ["spec.md", "contract.md"],
    "Ready for Dev": ["spec.md", "contract.md"],
    "Ready for QA": ["spec.md", "contract.md", "code"],
    "In Review": ["spec.md", "contract.md", "code", "test-plan.md"],
}

UPDATE_HOOK = """#!/bin/sh
ref="$1"; old="$2"; new="$3"
zero=0000000000000000000000000000000000000000
forced=false
if [ "$old" != "$zero" ] && [ "$new" != "$zero" ]; then
  git merge-base --is-ancestor "$old" "$new" || forced=true
fi
printf '{"ref":"%s","old":"%s","new":"%s","forced":%s,"epoch":%s}\\n' \\
  "$ref" "$old" "$new" "$forced" "$(date +%s)" >> "__LOG__"
exit 0
"""


def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path) as handle:
        return sum(1 for _ in handle)


def slug(text):
    words = "".join(ch if ch.isalnum() else " " for ch in text.lower()).split()
    return "-".join(words[:6])


def spec_text(ticket):
    return ("# %s\n\n**Source:** https://linear.app/acme/issue/%s\n\n## Problem\n\n%s\n\n"
            "## Success Criteria\n\n- The change described above works in the running app.\n"
            % (ticket["title"], ticket["id"], ticket.get("description") or ticket["title"]))


def contract_text(ticket):
    return ("# Contract: %s\n\n## Modules\n\n- `src/%s` — owns this change.\n\n## Behaviors\n\n"
            "- [ ] 1. The smallest end-to-end proof of the change.\n- [ ] 2. The rest of the change.\n\n"
            "## Anti-Behaviors\n\n- None.\n\n## Assumptions\n\n- None.\n%s"
            % (ticket["title"], ticket["id"].lower(), ticket.get("contract_extra", "")))


def artifact_files(ticket, names):
    files = {}
    for name in names:
        if name == "spec.md":
            files["workflows/%s/spec.md" % ticket["folder"]] = spec_text(ticket)
        elif name == "contract.md":
            files["workflows/%s/contract.md" % ticket["folder"]] = contract_text(ticket)
        elif name == "test-plan.md":
            files["workflows/%s/test-plan.md" % ticket["folder"]] = "# Test plan\n\n- Case 1: boundary.\n"
        elif name == "code":
            files["src/%s.txt" % ticket["id"].lower()] = "implementation of %s\n" % ticket["id"]
    return files


def default_workers(ticket):
    key = ticket["id"].lower()
    return {
        "architect": [{
            "status": "done", "summary": "fresh contract: workflows/{folder}/contract.md, two behaviors",
            "writes": {"workflows/{folder}/contract.md": contract_text(ticket)},
            "extra": {"assumptions": "none", "open_questions": "none"}}],
        "cto": [{
            "status": "done", "summary": "approved the contract with one ordering edit",
            "writes": {"workflows/{folder}/contract.md": contract_text(ticket) + "\n<!-- reviewed -->\n"},
            "extra": {"assumptions": "none"}}],
        "dev": [{
            "status": "done", "summary": "implemented behaviors 1-2",
            "writes": {"src/%s.txt" % key: "implementation of %s, round {index}\n" % ticket["id"]},
            "extra": {"verify": "PASS"}}],
        "qa": [{
            "status": "done", "summary": "12 cases, all green",
            "writes": {"workflows/{folder}/test-plan.md": "# Test plan\n\n- Case 1: boundary.\n",
                       "tests/%s.test.txt" % key: "adversarial tests, round {index}\n"},
            "extra": {"route": "in_review", "findings": "none"}}],
    }


class Context:
    def __init__(self, run_dir, seed):
        self.run_dir = run_dir
        self.repo = os.path.join(run_dir, "repo")
        self.origin = os.path.join(run_dir, "remotes", OWNER, REPO + ".git")
        self.state = os.path.join(run_dir, "state")
        self.seed = seed
        self.tickets = {}

    def git(self, *arguments, cwd=None, check=True):
        result = subprocess.run(["git"] + list(arguments), cwd=cwd or self.repo, capture_output=True, text=True)
        if check and result.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(arguments), result.stderr))
        return result.stdout.strip()

    def write(self, files, cwd=None):
        for path, content in files.items():
            target = os.path.join(cwd or self.repo, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w") as handle:
                handle.write(content)

    def commit_on(self, branch, files, message, base="main"):
        """Commit files on a branch (created from base when new), push it, and return to main."""
        exists = self.git("rev-parse", "--verify", "--quiet", "refs/heads/" + branch, check=False)
        if exists:
            self.git("switch", branch)
        else:
            self.git("switch", "-c", branch, base)
        self.write(files)
        self.git("add", "-A")
        self.git("commit", "-m", message)
        self.git("push", "origin", branch)
        sha = self.git("rev-parse", "HEAD")
        self.git("switch", "main")
        return sha


def normalise(ticket, by_id):
    ticket = dict(ticket)
    ticket.setdefault("labels", [])
    ticket.setdefault("project", "App")
    ticket.setdefault("blockedBy", [])
    ticket.setdefault("parent", None)
    name = slug(ticket["title"])
    ticket.setdefault("branch", "acme/%s-%s" % (ticket["id"].lower(), name))
    ticket.setdefault("folder", "2026-11-01-%s-%s" % (ticket["id"].lower(), name))
    return ticket


def scaffold(case_dir, run_dir, fakes_dir):
    with open(os.path.join(case_dir, "seed.json")) as handle:
        seed = json.load(handle)
    context = Context(run_dir, seed)
    os.makedirs(context.state)
    os.makedirs(os.path.dirname(context.origin))
    shutil.copytree(os.path.join(ROOT, "fixture"), context.repo)
    os.rename(os.path.join(context.repo, "_claude"), os.path.join(context.repo, ".claude"))
    harness = os.path.join(run_dir, "harness")
    os.makedirs(harness)
    for name in ("worker.py", "verify.py"):
        shutil.copy(os.path.join(HERE, name), harness)

    subprocess.run(["git", "init", "--bare", "-b", "main", context.origin], capture_output=True, check=True)
    hook = os.path.join(context.origin, "hooks", "update")
    with open(hook, "w") as handle:
        handle.write(UPDATE_HOOK.replace("__LOG__", os.path.join(context.state, "pushes.jsonl")))
    os.chmod(hook, os.stat(hook).st_mode | stat.S_IEXEC)

    context.git("init", "-b", "main")
    context.git("config", "user.name", "Dev Bot")
    context.git("config", "user.email", "dev-bot@example.invalid")
    context.git("remote", "add", "origin", context.origin)
    with open(os.path.join(context.repo, ".dev", "harness-path"), "w") as handle:
        handle.write(harness + "\n")

    tickets = [normalise(ticket, None) for ticket in seed["tickets"]]
    by_id = {ticket["id"]: ticket for ticket in tickets}
    for ticket in tickets:
        parent = by_id.get(ticket["parent"]) if ticket["parent"] else None
        ticket["lane_base"] = "origin/" + parent["branch"] if parent else "origin/main"
        ticket["is_epic"] = any(other["parent"] == ticket["id"] for other in tickets)
    context.tickets = by_id

    main_files = {}
    for ticket in tickets:
        names = ticket.get("artifacts", ARTIFACTS_BY_STATUS.get(ticket["status"], []))
        ticket["_artifacts"] = names
        if ticket["is_epic"] or ticket["parent"]:
            continue
        if names == ["spec.md"] and ticket.get("artifacts_on", "base") == "base":
            main_files.update(artifact_files(ticket, names))
    context.write(main_files)
    context.git("add", "-A")
    context.git("commit", "-m", "Pretend app")
    context.git("push", "origin", "main")

    for ticket in tickets:
        if not ticket["is_epic"]:
            continue
        files = {"workflows/%s/epic.md" % ticket["folder"]: "# %s\n" % ticket["title"]}
        for child in tickets:
            if child["parent"] == ticket["id"]:
                files.update(artifact_files(child, ["spec.md"]))
        context.commit_on(ticket["branch"], files, "%s: slice specs" % ticket["id"])

    for ticket in tickets:
        names = ticket["_artifacts"]
        if ticket["is_epic"] or not names:
            continue
        on_base = names == ["spec.md"] and ticket.get("artifacts_on", "base") == "base"
        if on_base:
            continue
        base = ticket["lane_base"].replace("origin/", "")
        context.commit_on(ticket["branch"], artifact_files(ticket, names),
                          "%s: %s" % (ticket["id"], ", ".join(names)), base=base)

    scenario = {
        "delay": seed.get("delay", 3),
        "verify": seed.get("verify", {}),
        "tickets": {ticket["id"]: {"branch": ticket["branch"], "folder": ticket["folder"],
                                   "lane_base": ticket["lane_base"]} for ticket in tickets},
        "workers": {},
    }
    for ticket in tickets:
        scripts = default_workers(ticket)
        for stage, override in (ticket.get("workers") or {}).items():
            rounds = override if isinstance(override, list) else [override]
            merged = []
            for entry in rounds:
                script = dict(scripts[stage][0])
                script.update(entry)
                if "extra" in entry:
                    script["extra"] = dict(scripts[stage][0].get("extra", {}), **entry["extra"])
                merged.append(script)
            scripts[stage] = merged
        scenario["workers"][ticket["id"]] = scripts
    with open(os.path.join(run_dir, "scenario.json"), "w") as handle:
        json.dump(scenario, handle, indent=1)

    stamp = "2026-11-01T09:00:00.000Z"
    linear = {
        "team": TEAM,
        "me": {"id": "user-1", "name": "Sam Operator", "email": "operator@example.invalid"},
        "statuses": [{"id": "status-" + slug(name), "type": kind, "name": name} for name, kind in STATUSES],
        "labels": [{"id": "label-" + slug(name), "name": name, "color": "#95a2b3", "description": None,
                    "archivedAt": None} for name in LABELS],
        "projects": [{"id": "project-" + slug(name), "name": name} for name in PROJECTS],
        "issues": {}, "comments": [], "history": [],
        "next_issue": 900, "next_comment": 1, "next_attachment": 1,
    }
    hidden = {}
    for position, ticket in enumerate(tickets):
        created = "2026-11-01T09:%02d:00.000Z" % position
        issues = hidden if ticket.get("hidden") else linear["issues"]
        issues[ticket["id"]] = {
            "id": ticket["id"], "uuid": "uuid-" + ticket["id"].lower(), "title": ticket["title"],
            "description": ticket.get("description", ""), "status": ticket["status"],
            "labels": list(ticket["labels"]), "parentId": ticket["parent"], "project": ticket["project"],
            "assignee": None, "blockedBy": list(ticket["blockedBy"]), "relatedTo": [], "attachments": [],
            "gitBranchName": ticket["branch"], "url": "https://linear.app/acme/issue/" + ticket["id"],
            "createdAt": created, "updatedAt": created,
        }
        if not ticket.get("hidden"):
            linear["history"].append({"at": stamp, "issue": ticket["id"], "status": ticket["status"],
                                      "labels": list(ticket["labels"])})
    with open(os.path.join(context.state, "linear.json"), "w") as handle:
        json.dump(linear, handle, indent=1)
    with open(os.path.join(context.state, "hidden.json"), "w") as handle:
        json.dump(hidden, handle, indent=1)
    github = {"owner": OWNER, "repo": REPO, "me": "sam-operator", "pulls": [], "next_pull": 1,
              "checks": (seed.get("github") or {}).get("checks", "pending")}
    for pull in (seed.get("github") or {}).get("pulls", []):
        github["pulls"].append(dict({"number": github["next_pull"], "body": "", "state": "open",
                                     "draft": False, "merged": False, "created_at": stamp,
                                     "updated_at": stamp}, **pull))
        github["next_pull"] += 1
    with open(os.path.join(context.state, "github.json"), "w") as handle:
        json.dump(github, handle, indent=1)

    setup_path = os.path.join(case_dir, "setup.py")
    if os.path.exists(setup_path):
        spec = importlib.util.spec_from_file_location("case_setup", setup_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.setup(context)

    pushes = os.path.join(context.state, "pushes.jsonl")
    with open(os.path.join(context.state, "seeded.json"), "w") as handle:
        json.dump({"pushes": count_lines(pushes)}, handle)

    def server(script, prefix):
        env = {"EVAL_%s_STATE" % prefix: os.path.join(context.state, prefix.lower() + ".json"),
               "EVAL_%s_CALLS" % prefix: os.path.join(context.state, prefix.lower() + "-calls.jsonl"),
               "EVAL_ORIGIN": context.origin}
        return {"command": "python3", "args": [os.path.join(fakes_dir, script)], "env": env}

    with open(os.path.join(run_dir, "mcp.json"), "w") as handle:
        json.dump({"mcpServers": {"linear": server("linear_mcp.py", "LINEAR"),
                                  "github": server("github_mcp.py", "GITHUB")}}, handle, indent=1)
    return context
