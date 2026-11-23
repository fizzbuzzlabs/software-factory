"""Build one worker run's world: the sample app as a repo with one seeded ticket, ready for one real agent.

A worker case directory holds:
  case.json      stage, ticket, folder, timeout, optional Linear comments
  seed/main/     files laid over the sample app on main (state that existed before the ticket)
  seed/branch/   files committed on the ticket branch (its workflows/ folder, and code for later stages)
  case.json      may also list `others`: in-flight tickets, each pushed on its own branch from main
  hidden/        request scripts the worker never sees, replayed against its result
  grade.py       grade(run) -> checks
"""

import json
import os
import shutil
import stat
import subprocess

import scaffold

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OWNER, REPO = "acme-labs", "reminders"
TRIGGER = {"architect": "Spec Done", "cto": "Contract Review", "dev": "Ready for Dev", "qa": "Ready for QA"}


def overlay(source, target):
    if not os.path.isdir(source):
        return
    for directory, _, files in os.walk(source):
        relative = os.path.relpath(directory, source)
        for name in files:
            destination = os.path.join(target, relative, name)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy(os.path.join(directory, name), destination)


def git(repo, *arguments):
    result = subprocess.run(["git"] + list(arguments), cwd=repo, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(arguments), result.stderr))
    return result.stdout.strip()


def scaffold_worker(case_dir, run_dir, fakes_dir, arm_plugin):
    with open(os.path.join(case_dir, "case.json")) as handle:
        case = json.load(handle)
    ticket = case["ticket"]
    stage = case["stage"]
    name = scaffold.slug(ticket["title"])
    branch = "acme/%s-%s" % (ticket["id"].lower(), name)
    folder = case["folder"]
    repo = os.path.join(run_dir, "repo")
    origin = os.path.join(run_dir, "remotes", OWNER, REPO + ".git")
    state = os.path.join(run_dir, "state")
    os.makedirs(state)
    os.makedirs(os.path.dirname(origin))

    shutil.copytree(os.path.join(ROOT, "sample-app"), repo,
                    ignore=shutil.ignore_patterns("node_modules", "reports", ".debt-reports", "coverage"))
    hidden_claude = os.path.join(repo, "_claude")
    if os.path.isdir(hidden_claude):
        os.rename(hidden_claude, os.path.join(repo, ".claude"))
    for name in case.get("main_overlays", []):
        overlay(os.path.join(os.path.dirname(case_dir), "_shared", "code", name), repo)
    overlay(os.path.join(case_dir, "seed", "main"), repo)
    for path in case.get("delete_on_main", []):
        os.remove(os.path.join(repo, path))

    subprocess.run(["git", "init", "--bare", "-b", "main", origin], capture_output=True, check=True)
    hook = os.path.join(origin, "hooks", "update")
    with open(hook, "w") as handle:
        handle.write(scaffold.UPDATE_HOOK.replace("__LOG__", os.path.join(state, "pushes.jsonl")))
    os.chmod(hook, os.stat(hook).st_mode | stat.S_IEXEC)

    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Dev Bot")
    git(repo, "config", "user.email", "dev-bot@example.invalid")
    git(repo, "remote", "add", "origin", origin)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "Reminders service")
    git(repo, "push", "origin", "main")

    git(repo, "switch", "-c", branch)
    for name in case.get("branch_overlays", []):
        overlay(os.path.join(os.path.dirname(case_dir), "_shared", "code", name), repo)
    overlay(os.path.join(case_dir, "seed", "branch"), repo)
    for path in case.get("delete_on_branch", []):
        os.remove(os.path.join(repo, path))
    for document in case.get("documents", []):
        with open(os.path.join(os.path.dirname(case_dir), document["from"])) as handle:
            text = handle.read()
        text = (text.replace("__FOLDER__", folder).replace("__TICKET__", ticket["id"])
                .replace("__BOX__", document.get("box", "[ ]")))
        for old, new in (document.get("replace") or {}).items():
            text = text.replace(old, new)
        destination = os.path.join(repo, "workflows", folder, document["to"])
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "w") as handle:
            handle.write(text)
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain"):
        git(repo, "commit", "-m", "%s: %s" % (ticket["id"], case.get("seed_message", "spec")))
    for step in case.get("branch_commits", []):
        overlay(os.path.join(case_dir, "seed", step["overlay"]), repo)
        git(repo, "add", "-A")
        git(repo, "commit", "-m", step["message"])
    git(repo, "push", "origin", branch)
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "main")
    others = []
    for other in case.get("others", []):
        other_branch = "acme/%s-%s" % (other["id"].lower(), scaffold.slug(other["title"]))
        git(repo, "switch", "-c", other_branch)
        for name in other.get("branch_overlays", []):
            overlay(os.path.join(os.path.dirname(case_dir), "_shared", "code", name), repo)
        for document in other.get("documents", []):
            with open(os.path.join(os.path.dirname(case_dir), document["from"])) as handle:
                text = handle.read()
            text = (text.replace("__FOLDER__", other["folder"]).replace("__TICKET__", other["id"])
                    .replace("__BOX__", document.get("box", "[ ]")))
            destination = os.path.join(repo, "workflows", other["folder"], document["to"])
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with open(destination, "w") as handle:
                handle.write(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-m", "%s: in-flight work" % other["id"])
        git(repo, "push", "origin", other_branch)
        git(repo, "switch", "main")
        others.append(dict(other, branch=other_branch))
    tree = os.path.join(repo, ".claude", "worktrees", "agent-%s-%s" % (ticket["id"].lower(), stage))
    git(repo, "worktree", "add", tree, "-B", branch, "origin/" + branch)

    stamp = "2026-11-01T09:00:00.000Z"
    status = ticket.get("status", TRIGGER[stage])
    linear = {
        "team": scaffold.TEAM,
        "me": {"id": "user-1", "name": "Sam Operator", "email": "operator@example.invalid"},
        "statuses": [{"id": "status-" + scaffold.slug(label), "type": kind, "name": label}
                     for label, kind in scaffold.STATUSES],
        "labels": [{"id": "label-" + scaffold.slug(label), "name": label, "color": "#95a2b3",
                    "description": None, "archivedAt": None} for label in scaffold.LABELS],
        "projects": [{"id": "project-app", "name": "App"}],
        "issues": {ticket["id"]: {
            "id": ticket["id"], "uuid": "uuid-" + ticket["id"].lower(), "title": ticket["title"],
            "description": ticket.get("description", ""), "status": status, "labels": ["in progress"],
            "parentId": None, "project": "App", "assignee": None, "blockedBy": [], "relatedTo": [],
            "attachments": [], "gitBranchName": branch,
            "url": "https://linear.app/acme/issue/" + ticket["id"], "createdAt": stamp, "updatedAt": stamp}},
        "comments": [], "history": [{"at": stamp, "issue": ticket["id"], "status": status,
                                     "labels": ["in progress"]}],
        "next_issue": 900, "next_comment": 1, "next_attachment": 1,
    }
    for other in others:
        linear["issues"][other["id"]] = {
            "id": other["id"], "uuid": "uuid-" + other["id"].lower(), "title": other["title"],
            "description": other.get("description", ""), "status": other["status"], "labels": [],
            "parentId": None, "project": "App", "assignee": None, "blockedBy": [], "relatedTo": [],
            "attachments": [], "gitBranchName": other["branch"],
            "url": "https://linear.app/acme/issue/" + other["id"], "createdAt": stamp, "updatedAt": stamp}
        linear["history"].append({"at": stamp, "issue": other["id"], "status": other["status"], "labels": []})
    for body in case.get("comments", []):
        linear["comments"].append({"id": "comment-%d" % linear["next_comment"], "issueId": ticket["id"],
                                   "body": body, "parentId": None, "createdAt": stamp, "updatedAt": stamp,
                                   "author": {"id": "user-1", "name": "Sam Operator"}})
        linear["next_comment"] += 1
    with open(os.path.join(state, "linear.json"), "w") as handle:
        json.dump(linear, handle, indent=1)
    with open(os.path.join(state, "github.json"), "w") as handle:
        json.dump({"owner": OWNER, "repo": REPO, "me": "sam-operator", "pulls": [], "next_pull": 1,
                   "checks": "pending"}, handle, indent=1)
    pushes = os.path.join(state, "pushes.jsonl")
    with open(os.path.join(state, "seeded.json"), "w") as handle:
        json.dump({"pushes": scaffold.count_lines(pushes), "base": base, "branch": branch,
                   "folder": folder, "ticket": ticket["id"], "stage": stage}, handle)

    def server(script, prefix):
        env = {"EVAL_%s_STATE" % prefix: os.path.join(state, prefix.lower() + ".json"),
               "EVAL_%s_CALLS" % prefix: os.path.join(state, prefix.lower() + "-calls.jsonl"),
               "EVAL_ORIGIN": origin}
        return {"command": "python3", "args": [os.path.join(fakes_dir, script)], "env": env}

    with open(os.path.join(run_dir, "mcp.json"), "w") as handle:
        json.dump({"mcpServers": {"linear": server("linear_mcp.py", "LINEAR"),
                                  "github": server("github_mcp.py", "GITHUB")}}, handle, indent=1)

    with open(os.path.join(ROOT, "worker-brief.md")) as handle:
        brief = handle.read()
    brief = (brief.replace("{lane}", REPO).replace("{branch}", branch).replace("{ticket}", ticket["id"])
             .replace("{worktree_isolation}", os.path.join(arm_plugin, "skills", "conventions",
                                                           "worktree-isolation.md")))
    extra = case.get("brief_context")
    if extra:
        brief = brief.rstrip() + "\n\n" + extra + "\n"
    return {"case": case, "repo": repo, "tree": tree, "origin": origin, "branch": branch, "base": base,
            "folder": folder, "brief": brief, "stage": stage}
