#!/usr/bin/env python3
"""Measure how often a skill's referenced conventions are in context when it runs.

Scans local Claude Code transcripts (~/.claude/projects/**/*.jsonl) for factory skill loads
(Skill tool calls and /<skill> commands) and, for every convention the skill's SKILL.md
references, counts the run as covered when the convention was Read, or injected by the
inject-conventions hook (a `<convention file="conventions/x.md">` tag), at any point in that
transcript before the skill's next load.

Usage: scripts/convention-coverage.py [--since YYYY-MM-DD]
"""
import collections
import datetime
import glob
import json
import os
import re
import sys

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills")
CONV = re.compile(r"conventions/([\w-]+)\.md")
INJECTED = re.compile(r'<convention file=\\?"conventions/([\w-]+)\.md')
CMD = re.compile(r"<command-name>/?(?:software-factory:)?([\w-]+)</command-name>")

since = None
if "--since" in sys.argv:
    since = datetime.datetime.fromisoformat(sys.argv[sys.argv.index("--since") + 1]).timestamp()

refs = {}
for p in glob.glob(os.path.join(SKILLS, "*", "SKILL.md")):
    refs[p.split(os.sep)[-2]] = sorted(set(CONV.findall(open(p).read())))

stats = collections.defaultdict(lambda: [0, 0, 0])  # runs, read, injected
for f in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
    if since and os.path.getmtime(f) < since:
        continue
    events = []
    for line in open(f, errors="replace"):
        if "conventions/" not in line and '"Skill"' not in line and "command-name" not in line:
            continue
        events += [("inject", m) for m in INJECTED.findall(line)]
        try:
            d = json.loads(line)
        except ValueError:
            continue
        content = (d.get("message") or {}).get("content")
        if isinstance(content, str):
            events += [("skill", m) for m in CMD.findall(content)]
            continue
        for c in content or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                inp = c.get("input") or {}
                if c.get("name") == "Skill":
                    events.append(("skill", str(inp.get("skill", "")).split(":")[-1]))
                elif c.get("name") in ("Read", "Bash", "Grep"):
                    txt = str(inp.get("file_path") or inp.get("command") or inp.get("path") or "")
                    events += [("read", m) for m in CONV.findall(txt)]
            elif c.get("type") == "text" and d.get("type") == "user":
                events += [("skill", m) for m in CMD.findall(c.get("text", ""))]
    for i, (kind, skill) in enumerate(events):
        if kind != "skill" or skill not in refs:
            continue
        end = next((j for j in range(i + 1, len(events)) if events[j] == ("skill", skill)), len(events))
        read = {v for k, v in events[:end] if k == "read"}
        injected = {v for k, v in events[:end] if k == "inject"}
        for conv in refs[skill]:
            s = stats[conv]
            s[0] += 1
            s[1] += conv in read and conv not in injected
            s[2] += conv in injected

print(f"{'convention':28} {'runs':>5} {'read':>5} {'inject':>6} {'covered':>8}")
for conv, (n, r, inj) in sorted(stats.items(), key=lambda kv: (kv[1][1] + kv[1][2]) / kv[1][0]):
    print(f"{conv:28} {n:5} {r:5} {inj:6} {100 * (r + inj) // n:7}%")
