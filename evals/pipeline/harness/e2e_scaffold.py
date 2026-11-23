"""Build one end-to-end run's world: a real app repo, rewound to before a shipped ticket, with fake boards.

An e2e case replays a ticket that already went through the pipeline. The sandbox is a fresh local
clone of the app repo whose `origin` is a local bare repo, so nothing reaches GitHub. Linear and
GitHub are the same fake MCP servers the other suites use, so nothing reaches the real boards
either. The workers are real, and so is the app's own tooling (its tests, its `verify` skill).

A case directory holds case.json:
  app             the app repo's directory name; looked up beside the factory's main checkout,
                  or under EVAL_APP_REPOS (a directory that holds app checkouts)
  ticket          { id, title, description }
  folder          the ticket's workflows/ folder name
  pool_merge      the commit on the app's main that merged the ticket ("Pool: <ID> ...")
  project         the Linear project the ticket sits in
  before_tests    commands the app's CI runs before its tests, such as a client build
  budget_usd      spending cap for the run, at API prices
  timeout_minutes
"""

import json
import os
import re
import stat
import subprocess

import scaffold

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def git(repo, *arguments, check=True):
    result = subprocess.run(["git"] + list(arguments), cwd=repo, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(arguments), result.stderr.strip()))
    return result.stdout.strip()


def find_app(name):
    """The app's local checkout: under EVAL_APP_REPOS, else beside the factory's main checkout."""
    common = git(ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir")
    beside = os.path.dirname(os.path.dirname(common))
    for parent in [os.environ.get("EVAL_APP_REPOS"), beside]:
        if parent and os.path.isdir(os.path.join(os.path.expanduser(parent), name, ".git")):
            return os.path.join(os.path.expanduser(parent), name)
    raise RuntimeError("no checkout of %s found; set EVAL_APP_REPOS to the directory that holds it" % name)


def origin_name(app):
    """owner and repo from the app's real origin URL, so the sandbox's origin path reads the same."""
    url = git(app, "remote", "get-url", "origin")
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", url)
    if not match:
        raise RuntimeError("can't read owner/repo from origin URL " + url)
    return match.group(1), match.group(2)


def strip_plugin_settings(repo):
    """The arm's plugin is loaded from a folder; the installed copy must not load beside it."""
    path = os.path.join(repo, ".claude", "settings.json")
    if not os.path.exists(path):
        return {}
    with open(path) as handle:
        settings = json.load(handle)
    for key in ("enabledPlugins", "extraKnownMarketplaces"):
        settings.pop(key, None)
    with open(path, "w") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")
    return settings


def scaffold_e2e(case_dir, run_dir, fakes_dir):
    with open(os.path.join(case_dir, "case.json")) as handle:
        case = json.load(handle)
    ticket = case["ticket"]
    app = find_app(case["app"])
    owner, name = origin_name(app)
    merge = case["pool_merge"]
    shipped = git(app, "rev-parse", merge + "^2")
    base = git(app, "merge-base", merge + "^1", merge + "^2")
    folder = case["folder"]
    spec = git(app, "show", "%s:workflows/%s/spec.md" % (shipped, folder))

    repo = os.path.join(run_dir, "repo")
    origin = os.path.join(run_dir, "remotes", owner, name + ".git")
    state = os.path.join(run_dir, "state")
    os.makedirs(state)
    os.makedirs(os.path.dirname(origin))
    subprocess.run(["git", "clone", "-q", "--no-local", "--no-checkout", app, repo], capture_output=True, check=True)
    subprocess.run(["git", "init", "--bare", "-b", "main", origin], capture_output=True, check=True)
    hook = os.path.join(origin, "hooks", "update")
    with open(hook, "w") as handle:
        handle.write(scaffold.UPDATE_HOOK.replace("__LOG__", os.path.join(state, "pushes.jsonl")))
    os.chmod(hook, os.stat(hook).st_mode | stat.S_IEXEC)

    git(repo, "config", "user.name", "Dev Bot")
    git(repo, "config", "user.email", "dev-bot@example.invalid")
    git(repo, "remote", "set-url", "origin", origin)
    for ref in git(repo, "for-each-ref", "--format=%(refname)", "refs/remotes/origin").split():
        git(repo, "update-ref", "-d", ref)
    git(repo, "checkout", "-q", "-B", "main", base)

    claude_md = os.path.join(repo, "CLAUDE.md")
    with open(claude_md) as handle:
        lines = handle.read().splitlines(keepends=True)
    with open(claude_md, "w") as handle:
        handle.writelines(line for line in lines if "Sibling repos:" not in line)
    settings = strip_plugin_settings(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Sandbox: one repo, plugin loaded from a folder")
    git(repo, "push", "-q", "origin", "main")
    start = git(repo, "rev-parse", "HEAD")

    branch = "acme/%s-%s" % (ticket["id"].lower(), scaffold.slug(ticket["title"]))
    git(repo, "switch", "-q", "-c", branch)
    spec_path = os.path.join(repo, "workflows", folder, "spec.md")
    os.makedirs(os.path.dirname(spec_path), exist_ok=True)
    with open(spec_path, "w") as handle:
        handle.write(spec + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Spec for %s" % ticket["id"])
    git(repo, "push", "-q", "origin", branch)
    git(repo, "switch", "-q", "main")
    git(repo, "branch", "-q", "-D", branch)

    env_file = os.environ.get("EVAL_APP_ENV")
    if env_file:
        os.symlink(os.path.abspath(os.path.expanduser(env_file)), os.path.join(repo, ".env"))

    team = case.get("team", {"id": "team-acme", "name": "Acme", "key": "ACME"})
    stamp = "2026-11-01T09:00:00.000Z"
    project = case.get("project", "App")
    linear = {
        "team": team,
        "me": {"id": "user-1", "name": "Sam Operator", "email": "operator@example.invalid"},
        "statuses": [{"id": "status-" + scaffold.slug(label), "type": kind, "name": label}
                     for label, kind in scaffold.STATUSES],
        "labels": [{"id": "label-" + scaffold.slug(label), "name": label, "color": "#95a2b3",
                    "description": None, "archivedAt": None} for label in scaffold.LABELS],
        "projects": [{"id": "project-" + scaffold.slug(label), "name": label} for label in {project, "Factory"}],
        "issues": {ticket["id"]: {
            "id": ticket["id"], "uuid": "uuid-" + ticket["id"].lower(), "title": ticket["title"],
            "description": ticket.get("description", ""), "status": case.get("start_status", "Spec Done"),
            "labels": [], "parentId": None, "project": project, "assignee": None, "blockedBy": [],
            "relatedTo": [], "attachments": [], "gitBranchName": branch,
            "url": "https://linear.app/sandbox/issue/" + ticket["id"], "createdAt": stamp, "updatedAt": stamp}},
        "comments": [], "history": [{"at": stamp, "issue": ticket["id"],
                                     "status": case.get("start_status", "Spec Done"), "labels": []}],
        "next_issue": 9000, "next_comment": 1, "next_attachment": 1,
    }
    with open(os.path.join(state, "linear.json"), "w") as handle:
        json.dump(linear, handle, indent=1)
    with open(os.path.join(state, "github.json"), "w") as handle:
        json.dump({"owner": owner, "repo": name, "me": "sam-operator", "pulls": [], "next_pull": 1,
                   "checks": "pending"}, handle, indent=1)
    with open(os.path.join(state, "seeded.json"), "w") as handle:
        json.dump({"pushes": scaffold.count_lines(os.path.join(state, "pushes.jsonl")), "ticket": ticket["id"],
                   "branch": branch, "folder": folder, "start": start, "app": app, "app_base": base,
                   "app_shipped": shipped, "owner": owner, "repo": name}, handle, indent=1)

    def server(script, prefix):
        env = {"EVAL_%s_STATE" % prefix: os.path.join(state, prefix.lower() + ".json"),
               "EVAL_%s_CALLS" % prefix: os.path.join(state, prefix.lower() + "-calls.jsonl"),
               "EVAL_ORIGIN": origin}
        return {"command": "python3", "args": [os.path.join(fakes_dir, script)], "env": env}

    with open(os.path.join(run_dir, "mcp.json"), "w") as handle:
        json.dump({"mcpServers": {"linear": server("linear_mcp.py", "LINEAR"),
                                  "github": server("github_mcp.py", "GITHUB")}}, handle, indent=1)
    return {"case": case, "repo": repo, "origin": origin, "branch": branch, "folder": folder,
            "allowed": (settings.get("permissions") or {}).get("allow", []),
            "has_env": bool(env_file)}
