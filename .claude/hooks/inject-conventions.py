#!/usr/bin/env python3
"""Inject the convention files a skill references when the skill loads.

Skills point at `conventions/<name>.md` files but nothing makes Claude read them. This hook
returns their text as `additionalContext` the moment a skill loads, so they are always in
context:

- `PostToolUse` on the `Skill` tool (Claude invoked the skill; `tool_input.skill`).
- `UserPromptExpansion` (the user typed `/<skill>`, which bypasses the Skill tool;
  `command_name`).
- `SessionStart` with source `compact` clears the dedupe state, since compaction drops the
  injected text.

References are followed transitively: a convention's own `conventions/x.md` or bare `x.md`
mentions pull in sibling convention files that exist. Each file is injected once per agent
per session (subagents keep their own context, so they are keyed by `agent_id`).

`additionalContext` is capped at 10,000 characters per hook (over it, Claude sees only a
2,000-character preview), so hooks.json registers this script once per slot (`argv[1]` = slot
index). Every slot builds the same text, splits it into chunks under the cap, and emits only
its own chunk. The first slot to fire for a load writes the plan (exclusive create) and updates
the dedupe state; the others read that plan, so they never race the state file.

Telemetry-grade: never blocks, always exits 0, swallows every error. Needs only python3.
"""
import json
import os
import re
import sys
import tempfile
import time

REF_RE = re.compile(r"conventions/([a-z0-9][a-z0-9-]*\.md)")
BARE_RE = re.compile(r"`([a-z0-9][a-z0-9-]*\.md)`")
CHUNK = 9500
STATE_DIR = os.path.join(tempfile.gettempdir(), "sf-inject-conventions")


def skill_dirs(cwd):
    roots = []
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        roots.append(os.path.join(plugin_root, "skills"))
    project = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    if project:
        roots.append(os.path.join(project, ".claude", "skills"))
    return roots


def find_skill(name, cwd):
    # Plugin skills arrive namespaced (`software-factory:workflow-implement`).
    name = name.split(":")[-1].strip().lstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        return None
    for root in skill_dirs(cwd):
        path = os.path.join(root, name, "SKILL.md")
        if os.path.isfile(path):
            return path
    return None


def collect(skill_md):
    conv_dir = os.path.join(os.path.dirname(os.path.dirname(skill_md)), "conventions")
    order, queue = [], []
    with open(skill_md, encoding="utf-8") as f:
        queue.extend(REF_RE.findall(f.read()))
    while queue:
        name = queue.pop(0)
        path = os.path.join(conv_dir, name)
        if name in order or not os.path.isfile(path):
            continue
        order.append(name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        queue.extend(REF_RE.findall(text) + BARE_RE.findall(text))
    return conv_dir, order


def state_path(data):
    key = "%s-%s" % (data.get("session_id", "nosession"), data.get("agent_id") or "main")
    return os.path.join(STATE_DIR, re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".json")


def main():
    data = json.load(sys.stdin)
    event = data.get("hook_event_name")
    if event == "SessionStart":
        if data.get("source") == "compact":
            prefix = re.sub(r"[^A-Za-z0-9_.-]", "_", data.get("session_id", "")) + "-"
            for f in os.listdir(STATE_DIR) if os.path.isdir(STATE_DIR) else []:
                if f.startswith(prefix):
                    os.remove(os.path.join(STATE_DIR, f))
        return
    if event == "PostToolUse":
        name = (data.get("tool_input") or {}).get("skill", "")
    elif event == "UserPromptExpansion":
        name = data.get("command_name", "")
    else:
        return
    skill_md = find_skill(name, data.get("cwd", ""))
    if not skill_md:
        return
    conv_dir, names = collect(skill_md)

    slot = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    os.makedirs(STATE_DIR, exist_ok=True)
    load_id = data.get("tool_use_id") or data.get("prompt_id") or name
    plan = state_path(data)[:-5] + "-plan-" + re.sub(r"[^A-Za-z0-9_.-]", "_", load_id) + ".json"
    try:
        fd = os.open(plan, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        fd = None
    if fd is not None:
        chunks = build_chunks(data, name, conv_dir, names)
        with os.fdopen(fd, "w") as f:
            json.dump(chunks, f)
    else:
        chunks = None
        for _ in range(40):
            try:
                with open(plan) as f:
                    chunks = json.load(f)
                break
            except Exception:
                time.sleep(0.05)
    if not chunks or slot >= len(chunks):
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event,
        "additionalContext": chunks[slot],
    }}))


def build_chunks(data, name, conv_dir, names):
    sp = state_path(data)
    try:
        with open(sp) as f:
            seen = set(json.load(f))
    except Exception:
        seen = set()
    fresh = [n for n in names if n not in seen]
    if not fresh:
        return []
    with open(sp, "w") as f:
        json.dump(sorted(seen | set(fresh)), f)

    text = []
    for n in fresh:
        with open(os.path.join(conv_dir, n), encoding="utf-8") as f:
            text.append('<convention file="conventions/%s">\n%s\n</convention>' % (n, f.read().strip()))
    body = "\n\n".join(text)
    pieces, cur = [], ""
    for line in body.splitlines(keepends=True):
        while len(line) > CHUNK:
            pieces.append(line[:CHUNK])
            line = line[CHUNK:]
        if len(cur) + len(line) > CHUNK:
            pieces.append(cur)
            cur = ""
        cur += line
    pieces.append(cur)
    header = (
        "Part %%d/%d of the conventions referenced by the `%s` skill, loaded by the "
        "software-factory inject-conventions hook (already in context; no need to Read them). "
        "Files: %s. Already loaded earlier this session: %s.\n\n"
        % (len(pieces), name.split(":")[-1], ", ".join(fresh),
           ", ".join(sorted(seen & set(names))) or "none")
    )
    return [header % (i + 1) + p for i, p in enumerate(pieces)]

if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
