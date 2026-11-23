#!/usr/bin/env python3
"""Fake Linear MCP server: one team, stateful issues, labels, relations and comments.

Tool names, argument names and response shapes follow the real Linear MCP server closely
enough that the factory skills run against it unchanged. State lives in the JSON file named
by EVAL_LINEAR_STATE; every call is appended to EVAL_LINEAR_CALLS.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_stdio import Server, ToolError
from store import Store, now

store = Store(os.environ["EVAL_LINEAR_STATE"], os.environ["EVAL_LINEAR_CALLS"])
server = Server("linear")

LIST_FIELDS = [
    "id", "title", "status", "statusType", "labels", "project", "parentId",
    "gitBranchName", "url", "createdAt", "updatedAt", "assignee", "team",
]


def _op(name, fields, required):
    properties = {"op": {"const": name, "type": "string"}}
    properties.update(fields)
    return {"type": "object", "properties": properties, "required": ["op"] + required}


_TEXT = {"type": "string", "minLength": 1}
PATCH_SCHEMA = {
    "type": "array", "minItems": 1, "maxItems": 50,
    "description": "Partial edits applied to the current content, in order and atomically (one failing "
                   "operation aborts the whole save). Every anchor string must match the current content "
                   "exactly once. Only valid on update, in place of the full description field",
    "items": {"oneOf": [
        _op("replace", {"old_string": dict(_TEXT, description="Exact text to replace. Must match exactly once"),
                        "new_string": {"type": "string", "description": "Replacement text. Empty string deletes the match"},
                        "replace_all": {"type": "boolean"}}, ["old_string", "new_string"]),
        _op("insert_before", {"anchor": dict(_TEXT, description="Exact text to insert before. Must match exactly once"),
                              "text": dict(_TEXT, description="Text to insert directly before the anchor")},
            ["anchor", "text"]),
        _op("insert_after", {"anchor": dict(_TEXT, description="Exact text to insert after. Must match exactly once"),
                             "text": dict(_TEXT, description="Text to insert directly after the anchor")},
            ["anchor", "text"]),
        _op("prepend", {"text": _TEXT}, ["text"]),
        _op("append", {"text": _TEXT}, ["text"]),
        _op("replace_range", {"from": dict(_TEXT, description="Exact text where the range starts (inclusive). Must match exactly once"),
                              "to": dict(_TEXT, description="Exact text where the range ends (exclusive, stays in place). Must match exactly once after `from`"),
                              "new_string": {"type": "string", "description": "Text replacing the range. Empty string deletes it"}},
            ["from", "to", "new_string"]),
    ]},
}


def find_status(state, wanted):
    lowered = str(wanted).lower()
    for status in state["statuses"]:
        if lowered in (status["name"].lower(), status["id"].lower()):
            return [status]
    return [status for status in state["statuses"] if status["type"] == lowered]


def status_type(state, name):
    for status in state["statuses"]:
        if status["name"] == name:
            return status["type"]
    return None


def resolve_issue(state, wanted):
    if wanted is None:
        raise ToolError("Issue id is required")
    key = str(wanted).upper()
    if key in state["issues"]:
        return state["issues"][key]
    for issue in state["issues"].values():
        if issue["uuid"] == wanted:
            return issue
    raise ToolError("Entity not found: Issue - Could not find referenced Issue: " + str(wanted))


def check_team(state, wanted):
    if wanted is None:
        return
    team = state["team"]
    if str(wanted).lower() not in (team["name"].lower(), team["id"].lower(), team["key"].lower()):
        raise ToolError("Team not found: " + str(wanted))


def label_name(state, wanted):
    lowered = str(wanted).lower()
    for label in state["labels"]:
        if lowered in (label["name"].lower(), label["id"].lower()):
            return label["name"]
    raise ToolError("Label not found: " + str(wanted))


def project_name(state, wanted):
    lowered = str(wanted).lower()
    for project in state["projects"]:
        if lowered in (project["name"].lower(), project["id"].lower()):
            return project["name"]
    raise ToolError("Project not found: " + str(wanted))


def render(state, issue, relations=False):
    view = {
        "id": issue["id"],
        "uuid": issue["uuid"],
        "title": issue["title"],
        "description": issue.get("description", ""),
        "url": issue["url"],
        "gitBranchName": issue["gitBranchName"],
        "createdAt": issue["createdAt"],
        "updatedAt": issue["updatedAt"],
        "status": issue["status"],
        "statusType": status_type(state, issue["status"]),
        "labels": list(issue["labels"]),
        "attachments": list(issue.get("attachments", [])),
        "assignee": issue.get("assignee"),
        "project": issue.get("project"),
        "parentId": issue.get("parentId"),
        "team": state["team"]["name"],
        "teamId": state["team"]["id"],
    }
    if relations:
        def brief(ids):
            return [{"id": other, "title": state["issues"][other]["title"]}
                    for other in ids if other in state["issues"]]

        blocks = [other["id"] for other in state["issues"].values()
                  if issue["id"] in other.get("blockedBy", [])]
        view["relations"] = {
            "blocks": brief(blocks),
            "blockedBy": brief(issue.get("blockedBy", [])),
            "relatedTo": brief(issue.get("relatedTo", [])),
            "duplicateOf": None,
        }
    return view


def pick(view, fields):
    if not fields:
        return view
    chosen = {"id": view["id"]}
    for field in fields:
        chosen[field] = view.get(field)
    return chosen


def apply_patch(text, operations):
    def once(anchor):
        count = text.count(anchor)
        if count != 1:
            raise ToolError("Patch anchor must match exactly once; matched %d times: %r" % (count, anchor[:80]))
        return text.index(anchor)

    needed = {"replace": ["old_string", "new_string"], "insert_before": ["anchor", "text"],
              "insert_after": ["anchor", "text"], "prepend": ["text"], "append": ["text"],
              "replace_range": ["from", "to", "new_string"]}
    for operation in operations:
        kind = operation.get("op")
        missing = [field for field in needed.get(kind, []) if field not in operation]
        if missing:
            raise ToolError("Invalid patch operation %r: missing %s" % (kind, ", ".join(missing)))
        if kind == "replace":
            if operation.get("replace_all"):
                if operation["old_string"] not in text:
                    raise ToolError("Patch anchor not found: %r" % operation["old_string"][:80])
                text = text.replace(operation["old_string"], operation["new_string"])
            else:
                start = once(operation["old_string"])
                text = text[:start] + operation["new_string"] + text[start + len(operation["old_string"]):]
        elif kind == "insert_before":
            start = once(operation["anchor"])
            text = text[:start] + operation["text"] + text[start:]
        elif kind == "insert_after":
            start = once(operation["anchor"]) + len(operation["anchor"])
            text = text[:start] + operation["text"] + text[start:]
        elif kind == "prepend":
            text = operation["text"] + text
        elif kind == "append":
            text = text + operation["text"]
        elif kind == "replace_range":
            start = once(operation["from"])
            rest = text[start + len(operation["from"]):]
            if rest.count(operation["to"]) != 1:
                raise ToolError("Patch range end must match exactly once after its start: %r" % operation["to"][:80])
            end = start + len(operation["from"]) + rest.index(operation["to"])
            text = text[:start] + operation["new_string"] + text[end:]
        else:
            raise ToolError("Unknown patch op: " + str(kind))
    return text


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


@server.tool("list_teams", "List teams in the user's Linear workspace",
             {"query": {"type": "string"}, "limit": {"type": "number"}})
@logged("list_teams")
def list_teams(arguments):
    team = store.read()["team"]
    return {"teams": [team], "hasNextPage": False}


@server.tool("get_team", "Retrieve details of a specific Linear team",
             {"query": {"type": "string", "description": "Team name, key, or ID"}}, ["query"])
@logged("get_team")
def get_team(arguments):
    state = store.read()
    check_team(state, arguments.get("query"))
    return state["team"]


@server.tool("list_issue_statuses", "List available issue statuses in a Linear team",
             {"team": {"type": "string", "description": "Team name or ID"}}, ["team"])
@logged("list_issue_statuses")
def list_issue_statuses(arguments):
    state = store.read()
    check_team(state, arguments.get("team"))
    return state["statuses"]


@server.tool("list_issue_labels", "List available issue labels in a Linear workspace or team",
             {"team": {"type": "string"}, "name": {"type": "string"}, "limit": {"type": "number"}})
@logged("list_issue_labels")
def list_issue_labels(arguments):
    state = store.read()
    check_team(state, arguments.get("team"))
    labels = state["labels"]
    if arguments.get("name"):
        labels = [label for label in labels if arguments["name"].lower() in label["name"].lower()]
    return {"labels": labels, "hasNextPage": False}


@server.tool("create_issue_label", "Create a new Linear issue label",
             {"name": {"type": "string"}, "team": {"type": "string"}, "description": {"type": "string"},
              "color": {"type": "string"}}, ["name"])
@logged("create_issue_label")
def create_issue_label(arguments):
    state = store.read()
    label = {"id": "label-%d" % (len(state["labels"]) + 1), "name": arguments["name"],
             "color": arguments.get("color", "#95a2b3"), "description": arguments.get("description"),
             "archivedAt": None}
    state["labels"].append(label)
    store.write(state)
    return label


@server.tool("list_projects", "List projects in the user's Linear workspace",
             {"team": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "number"}})
@logged("list_projects")
def list_projects(arguments):
    return {"projects": store.read()["projects"], "hasNextPage": False}


@server.tool("get_user", "Retrieve details of a specific Linear user",
             {"query": {"type": "string", "description": "User ID, name, email, or \"me\""}}, ["query"])
@logged("get_user")
def get_user(arguments):
    return store.read()["me"]


@server.tool(
    "list_issues",
    "List issues in the user's Linear workspace. For issues assigned to me, use \"me\" as the assignee.",
    {
        "team": {"type": "string", "description": "Team name or ID"},
        "state": {"type": "string", "description": "State type, name, or ID"},
        "label": {"type": "string", "description": "Label name or ID"},
        "parentId": {"type": "string", "description": "Parent issue ID or identifier (e.g., LIN-123)"},
        "project": {"type": "string", "description": "Project name or ID"},
        "assignee": {"type": ["string", "null"]},
        "query": {"type": "string", "description": "Search issue title or description"},
        "fields": {"type": "array", "items": {"type": "string"},
                   "description": "Fields to include in each result. `id` is always included."},
        "limit": {"type": "number"},
        "cursor": {"type": "string"},
        "orderBy": {"type": "string", "enum": ["createdAt", "updatedAt"]},
        "includeArchived": {"type": "boolean"},
        "updatedAt": {"type": "string"},
        "createdAt": {"type": "string"},
    },
)
@logged("list_issues")
def list_issues(arguments):
    state = store.read()
    check_team(state, arguments.get("team"))
    issues = list(state["issues"].values())
    if arguments.get("state"):
        names = [status["name"] for status in find_status(state, arguments["state"])]
        if not names:
            raise ToolError("State not found: " + str(arguments["state"]))
        issues = [issue for issue in issues if issue["status"] in names]
    if arguments.get("label"):
        wanted = label_name(state, arguments["label"])
        issues = [issue for issue in issues if wanted in issue["labels"]]
    if arguments.get("parentId"):
        parent = resolve_issue(state, arguments["parentId"])["id"]
        issues = [issue for issue in issues if issue.get("parentId") == parent]
    if arguments.get("project"):
        wanted = project_name(state, arguments["project"])
        issues = [issue for issue in issues if issue.get("project") == wanted]
    if arguments.get("query"):
        needle = arguments["query"].lower()
        issues = [issue for issue in issues
                  if needle in issue["title"].lower() or needle in issue.get("description", "").lower()]
    order = arguments.get("orderBy", "updatedAt")
    issues.sort(key=lambda issue: issue[order], reverse=True)
    fields = arguments.get("fields") or LIST_FIELDS
    return {"issues": [pick(render(state, issue), fields) for issue in issues], "hasNextPage": False}


@server.tool(
    "get_issue",
    "Retrieve detailed information about an issue by ID, including attachments and git branch name.",
    {
        "id": {"type": "string", "description": "Issue ID or identifier (e.g., LIN-123)"},
        "includeRelations": {"type": "boolean", "description": "Include blocking/related/duplicate relations"},
        "fields": {"type": "array", "items": {"type": "string"}},
    },
    ["id"],
)
@logged("get_issue")
def get_issue(arguments):
    state = store.read()
    issue = resolve_issue(state, arguments.get("id"))
    fields = arguments.get("fields") or []
    relations = bool(arguments.get("includeRelations")) or "relations" in fields
    return pick(render(state, issue, relations), fields)


@server.tool(
    "save_issue",
    "Create or update a Linear issue. If `id` is provided, updates the existing issue; otherwise creates "
    "a new one. When creating, `team` and `title` are required.",
    {
        "id": {"type": "string", "description": "Only for updating an existing issue."},
        "team": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "state": {"type": "string", "description": "State type, name, or ID"},
        "labels": {"type": "array", "items": {"type": "string"},
                   "description": "Replaces the full label set."},
        "addLabels": {"type": "array", "items": {"type": "string"}},
        "removeLabels": {"type": "array", "items": {"type": "string"}},
        "project": {"type": ["string", "null"]},
        "parentId": {"type": ["string", "null"]},
        "assignee": {"type": ["string", "null"]},
        "priority": {"type": "number"},
        "blockedBy": {"type": "array", "items": {"type": "string"}},
        "blocks": {"type": "array", "items": {"type": "string"}},
        "relatedTo": {"type": "array", "items": {"type": "string"}},
        "removeBlockedBy": {"type": "array", "items": {"type": "string"}},
        "links": {"type": "array", "items": {"type": "object"}},
        "patch": PATCH_SCHEMA,
    },
)
@logged("save_issue")
def save_issue(arguments):
    state = store.read()
    stamp = now()
    if arguments.get("id"):
        issue = resolve_issue(state, arguments["id"])
    else:
        check_team(state, arguments.get("team"))
        if not arguments.get("team") or not arguments.get("title"):
            raise ToolError("team and title are required when creating an issue")
        number = state["next_issue"]
        state["next_issue"] = number + 1
        key = "%s-%d" % (state["team"]["key"], number)
        slug = "-".join("".join(ch if ch.isalnum() else " " for ch in arguments["title"].lower()).split()[:7])
        issue = {
            "id": key, "uuid": "uuid-" + key.lower(), "title": arguments["title"], "description": "",
            "status": "Backlog", "labels": [], "parentId": None, "project": None, "assignee": None,
            "blockedBy": [], "relatedTo": [], "attachments": [],
            "gitBranchName": "acme/%s-%s" % (key.lower(), slug),
            "url": "https://linear.app/acme/issue/" + key, "createdAt": stamp, "updatedAt": stamp,
        }
        state["issues"][key] = issue

    if "title" in arguments and arguments.get("id"):
        issue["title"] = arguments["title"]
    if "description" in arguments:
        if "patch" in arguments:
            raise ToolError("patch cannot be combined with description")
        issue["description"] = arguments["description"]
    if "patch" in arguments:
        issue["description"] = apply_patch(issue.get("description", ""), arguments["patch"])
    if arguments.get("state"):
        matches = find_status(state, arguments["state"])
        if len(matches) != 1:
            raise ToolError("State not found or ambiguous: " + str(arguments["state"]))
        issue["status"] = matches[0]["name"]
    if "labels" in arguments:
        if "addLabels" in arguments or "removeLabels" in arguments:
            raise ToolError("labels cannot be combined with addLabels/removeLabels")
        issue["labels"] = [label_name(state, label) for label in arguments["labels"]]
    for label in arguments.get("addLabels", []):
        name = label_name(state, label)
        if name not in issue["labels"]:
            issue["labels"].append(name)
    for label in arguments.get("removeLabels", []):
        name = label_name(state, label)
        if name in issue["labels"]:
            issue["labels"].remove(name)
    if "project" in arguments:
        issue["project"] = project_name(state, arguments["project"]) if arguments["project"] else None
    if "parentId" in arguments:
        issue["parentId"] = resolve_issue(state, arguments["parentId"])["id"] if arguments["parentId"] else None
    if "assignee" in arguments:
        issue["assignee"] = state["me"]["name"] if arguments["assignee"] else None
    for other in arguments.get("blockedBy", []):
        blocker = resolve_issue(state, other)["id"]
        if blocker not in issue["blockedBy"]:
            issue["blockedBy"].append(blocker)
    for other in arguments.get("removeBlockedBy", []):
        blocker = resolve_issue(state, other)["id"]
        if blocker in issue["blockedBy"]:
            issue["blockedBy"].remove(blocker)
    for other in arguments.get("blocks", []):
        blocked = resolve_issue(state, other)
        if issue["id"] not in blocked["blockedBy"]:
            blocked["blockedBy"].append(issue["id"])
    for other in arguments.get("relatedTo", []):
        related = resolve_issue(state, other)["id"]
        if related not in issue["relatedTo"]:
            issue["relatedTo"].append(related)
    for link in arguments.get("links", []):
        issue["attachments"].append({"id": "attachment-%d" % state["next_attachment"],
                                     "title": link.get("title"), "subtitle": None, "url": link.get("url")})
        state["next_attachment"] += 1
    issue["updatedAt"] = stamp
    state["history"].append({"at": stamp, "issue": issue["id"], "status": issue["status"],
                             "labels": list(issue["labels"])})
    store.write(state)
    return render(state, issue)


@server.tool(
    "save_comment",
    "Create or update a comment on a Linear issue. Pass `body` and `issueId` to start a new thread.",
    {
        "issueId": {"type": "string", "description": "Issue ID or identifier (e.g., LIN-123)"},
        "body": {"type": "string", "description": "Content as Markdown"},
        "id": {"type": "string", "description": "Comment ID. If provided, updates the existing comment"},
        "parentId": {"type": "string", "description": "Parent comment ID (for replies)"},
    },
    ["body"],
)
@logged("save_comment")
def save_comment(arguments):
    state = store.read()
    stamp = now()
    if arguments.get("id"):
        for comment in state["comments"]:
            if comment["id"] == arguments["id"]:
                comment["body"] = arguments["body"]
                comment["updatedAt"] = stamp
                store.write(state)
                return comment
        raise ToolError("Comment not found: " + arguments["id"])
    if arguments.get("parentId"):
        parents = [comment for comment in state["comments"] if comment["id"] == arguments["parentId"]]
        if not parents:
            raise ToolError("Parent comment not found: " + arguments["parentId"])
        issue_id = parents[0]["issueId"]
    else:
        issue_id = resolve_issue(state, arguments.get("issueId"))["id"]
    comment = {"id": "comment-%d" % state["next_comment"], "issueId": issue_id, "body": arguments["body"],
               "parentId": arguments.get("parentId"), "createdAt": stamp, "updatedAt": stamp,
               "author": {"id": state["me"]["id"], "name": state["me"]["name"]}}
    state["next_comment"] += 1
    state["comments"].append(comment)
    store.write(state)
    return comment


@server.tool(
    "list_comments",
    "List comments on a Linear issue.",
    {"issueId": {"type": "string"}, "limit": {"type": "number"}, "cursor": {"type": "string"},
     "orderBy": {"type": "string"}},
)
@logged("list_comments")
def list_comments(arguments):
    state = store.read()
    issue_id = resolve_issue(state, arguments.get("issueId"))["id"]
    comments = [comment for comment in state["comments"] if comment["issueId"] == issue_id]
    comments.sort(key=lambda comment: comment["createdAt"], reverse=True)
    return {"comments": comments, "hasNextPage": False}


@server.tool("get_attachment", "Retrieve an issue attachment by ID", {"id": {"type": "string"}}, ["id"])
@logged("get_attachment")
def get_attachment(arguments):
    for issue in store.read()["issues"].values():
        for attachment in issue.get("attachments", []):
            if attachment["id"] == arguments["id"]:
                return attachment
    raise ToolError("Attachment not found: " + str(arguments.get("id")))


@server.tool("delete_attachment", "Delete an issue attachment by ID", {"id": {"type": "string"}}, ["id"])
@logged("delete_attachment")
def delete_attachment(arguments):
    state = store.read()
    for issue in state["issues"].values():
        kept = [attachment for attachment in issue.get("attachments", []) if attachment["id"] != arguments["id"]]
        if len(kept) != len(issue.get("attachments", [])):
            issue["attachments"] = kept
            store.write(state)
            return {"success": True}
    raise ToolError("Attachment not found: " + str(arguments.get("id")))


if __name__ == "__main__":
    server.serve()
