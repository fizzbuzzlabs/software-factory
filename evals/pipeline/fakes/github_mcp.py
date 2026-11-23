#!/usr/bin/env python3
"""Fake GitHub MCP server: pull requests for one repository whose branches live in a local bare repo.

Branch existence and "no commits between" are checked against the bare repo named by
EVAL_ORIGIN, the way GitHub checks a real push. State lives in EVAL_GITHUB_STATE; every call
is appended to EVAL_GITHUB_CALLS.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_stdio import Server, ToolError
from store import Store, now

store = Store(os.environ["EVAL_GITHUB_STATE"], os.environ["EVAL_GITHUB_CALLS"])
origin = os.environ["EVAL_ORIGIN"]
server = Server("github")

REPO = {"owner": {"type": "string", "description": "Repository owner"},
        "repo": {"type": "string", "description": "Repository name"}}


def sha_of(branch):
    result = subprocess.run(["git", "--git-dir", origin, "rev-parse", "--verify", "--quiet",
                             "refs/heads/" + branch], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def check_repo(state, arguments):
    if (arguments.get("owner"), arguments.get("repo")) != (state["owner"], state["repo"]):
        raise ToolError("failed to resolve repository: 404 Not Found: %s/%s"
                        % (arguments.get("owner"), arguments.get("repo")))


def branch_of(head):
    return head.split(":", 1)[1] if ":" in head else head


def render(state, pull):
    view = dict(pull)
    view["head"] = {"ref": pull["head"], "label": "%s:%s" % (state["owner"], pull["head"]),
                    "sha": sha_of(pull["head"])}
    view["base"] = {"ref": pull["base"], "label": "%s:%s" % (state["owner"], pull["base"])}
    view["html_url"] = "https://github.com/%s/%s/pull/%d" % (state["owner"], state["repo"], pull["number"])
    view["user"] = {"login": state["me"]}
    return view


def find_pull(state, number):
    for pull in state["pulls"]:
        if pull["number"] == int(number):
            return pull
    raise ToolError("failed to get pull request: 404 Not Found")


def logged(name):
    def wrap(handler):
        def run(arguments):
            try:
                with store.locked():
                    result = handler(arguments)
            except ToolError as error:
                store.log(name, arguments, str(error))
                raise
            store.log(name, arguments)
            return result

        return run

    return wrap


@server.tool("get_me", "Get details of the authenticated GitHub user.")
@logged("get_me")
def get_me(arguments):
    return {"login": store.read()["me"]}


@server.tool(
    "list_pull_requests",
    "List pull requests in a GitHub repository.",
    dict(REPO, head={"type": "string", "description": "Filter by head user/org and branch"},
         base={"type": "string", "description": "Filter by base branch"},
         state={"type": "string", "enum": ["open", "closed", "all"]},
         fields={"type": "array", "items": {"type": "string"}},
         page={"type": "number"}, perPage={"type": "number"},
         sort={"type": "string"}, direction={"type": "string"}),
    ["owner", "repo"],
)
@logged("list_pull_requests")
def list_pull_requests(arguments):
    state = store.read()
    check_repo(state, arguments)
    wanted = arguments.get("state", "open")
    pulls = [pull for pull in state["pulls"] if wanted == "all" or pull["state"] == wanted]
    if arguments.get("head"):
        pulls = [pull for pull in pulls if pull["head"] == branch_of(arguments["head"])]
    if arguments.get("base"):
        pulls = [pull for pull in pulls if pull["base"] == arguments["base"]]
    views = [render(state, pull) for pull in pulls]
    if arguments.get("fields"):
        views = [{field: view.get(field) for field in set(arguments["fields"]) | {"number"}} for view in views]
    return views


@server.tool(
    "create_pull_request",
    "Create a new pull request in a GitHub repository.",
    dict(REPO, title={"type": "string"}, head={"type": "string", "description": "Branch containing changes"},
         base={"type": "string", "description": "Branch to merge into"}, body={"type": "string"},
         draft={"type": "boolean", "description": "Create as draft PR"}),
    ["owner", "repo", "title", "head", "base"],
)
@logged("create_pull_request")
def create_pull_request(arguments):
    state = store.read()
    check_repo(state, arguments)
    head = branch_of(arguments["head"])
    base = arguments["base"]
    head_sha, base_sha = sha_of(head), sha_of(base)
    if head_sha is None:
        raise ToolError("failed to create pull request: 422 Validation Failed [{Resource:PullRequest "
                        "Field:head Code:invalid}]")
    if base_sha is None:
        raise ToolError("failed to create pull request: 422 Validation Failed [{Resource:PullRequest "
                        "Field:base Code:invalid}]")
    if head_sha == base_sha:
        raise ToolError("failed to create pull request: 422 Validation Failed: No commits between %s and %s"
                        % (base, head))
    for pull in state["pulls"]:
        if pull["state"] == "open" and pull["head"] == head and pull["base"] == base:
            raise ToolError("failed to create pull request: 422 Validation Failed: A pull request already "
                            "exists for %s:%s." % (state["owner"], head))
    stamp = now()
    pull = {"number": state["next_pull"], "title": arguments["title"], "body": arguments.get("body", ""),
            "head": head, "base": base, "state": "open", "draft": bool(arguments.get("draft")),
            "merged": False, "created_at": stamp, "updated_at": stamp}
    state["next_pull"] += 1
    state["pulls"].append(pull)
    store.write(state)
    return render(state, pull)


@server.tool(
    "update_pull_request",
    "Update an existing pull request in a GitHub repository.",
    dict(REPO, pullNumber={"type": "number"}, title={"type": "string"}, body={"type": "string"},
         state={"type": "string", "enum": ["open", "closed"]}, base={"type": "string"},
         draft={"type": "boolean", "description": "Mark pull request as draft (true) or ready for review (false)"}),
    ["owner", "repo", "pullNumber"],
)
@logged("update_pull_request")
def update_pull_request(arguments):
    state = store.read()
    check_repo(state, arguments)
    pull = find_pull(state, arguments["pullNumber"])
    for field in ("title", "body", "state", "base", "draft"):
        if field in arguments:
            pull[field] = arguments[field]
    pull["updated_at"] = now()
    store.write(state)
    return render(state, pull)


@server.tool(
    "pull_request_read",
    "Get information on a specific pull request in GitHub repository.",
    dict(REPO, pullNumber={"type": "number"},
         method={"type": "string", "enum": ["get", "get_diff", "get_status", "get_files", "get_commits",
                                             "get_reviews", "get_comments", "get_check_runs"]}),
    ["method", "owner", "repo", "pullNumber"],
)
@logged("pull_request_read")
def pull_request_read(arguments):
    state = store.read()
    check_repo(state, arguments)
    pull = find_pull(state, arguments["pullNumber"])
    method = arguments["method"]
    if method == "get":
        return render(state, pull)
    if method == "get_status":
        return {"state": state["checks"], "statuses": [], "total_count": 0, "sha": sha_of(pull["head"])}
    if method == "get_check_runs":
        status = "in_progress" if state["checks"] == "pending" else "completed"
        conclusion = None if state["checks"] == "pending" else state["checks"]
        return {"total_count": 1, "check_runs": [{"name": "ci", "status": status, "conclusion": conclusion}]}
    if method == "get_files":
        diff = subprocess.run(["git", "--git-dir", origin, "diff", "--name-only",
                               "refs/heads/%s...refs/heads/%s" % (pull["base"], pull["head"])],
                              capture_output=True, text=True)
        return [{"filename": name} for name in diff.stdout.split()]
    if method == "get_commits":
        log = subprocess.run(["git", "--git-dir", origin, "log", "--format=%H %s",
                              "refs/heads/%s..refs/heads/%s" % (pull["base"], pull["head"])],
                             capture_output=True, text=True)
        return [{"sha": line.split(" ", 1)[0], "commit": {"message": line.split(" ", 1)[1]}}
                for line in log.stdout.splitlines() if " " in line]
    return []


@server.tool(
    "merge_pull_request",
    "Merge a pull request in a GitHub repository.",
    dict(REPO, pullNumber={"type": "number"}, merge_method={"type": "string"},
         commit_title={"type": "string"}, commit_message={"type": "string"}),
    ["owner", "repo", "pullNumber"],
)
@logged("merge_pull_request")
def merge_pull_request(arguments):
    raise ToolError("failed to merge pull request: 405 Method Not Allowed: protected branch")


@server.tool("list_branches", "List branches in a GitHub repository", dict(REPO), ["owner", "repo"])
@logged("list_branches")
def list_branches(arguments):
    state = store.read()
    check_repo(state, arguments)
    refs = subprocess.run(["git", "--git-dir", origin, "for-each-ref", "--format=%(refname:short) %(objectname)",
                           "refs/heads"], capture_output=True, text=True)
    return [{"name": line.split(" ")[0], "commit": {"sha": line.split(" ")[1]}}
            for line in refs.stdout.splitlines() if " " in line]


if __name__ == "__main__":
    server.serve()
