#!/usr/bin/env python3
"""Stop hook: advisory nudge to bump the plugin version.

Registered only in this repo's .claude/settings.json; it doesn't ship in hooks.json.

The version in plugin/.claude-plugin/plugin.json is the cache-buster consuming repos key
on. If shipped paths (.claude/skills, agents, hooks) are committed on this branch without
a version bump, the change won't reach them, so this says so before the PR opens. It only
surfaces a systemMessage and never blocks the stop; the plugin-version-bump CI check is
the real gate.

It compares committed changes against the base branch, not the dirty worktree, so it stays
quiet mid-edit.
"""
import json
import os
import subprocess
import sys

BASE = "main"
MANIFEST = "plugin/.claude-plugin/plugin.json"
# .claude/hooks ships wholesale, but the repo-only hooks aren't in hooks.json and have no
# downstream effect.
SHIPPED = [
    ".claude/skills", ".claude/agents", ".claude/hooks",
    ":(exclude).claude/hooks/guard-protected-paths.py",
    ":(exclude).claude/hooks/require-version-bump.py",
]


def git(*args):
    """stdout of a git command, or None when it fails."""
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def version(manifest_json):
    try:
        v = json.loads(manifest_json).get("version")
    except (TypeError, ValueError, AttributeError):
        return ""
    return v if isinstance(v, str) else ""


def main():
    os.chdir(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
    merge_base = git("merge-base", BASE, "HEAD")
    if not merge_base:
        return  # no base, or detached: nothing to compare against
    changed = git("diff", "--name-only", f"{merge_base.strip()}...HEAD", "--", *SHIPPED)
    if not changed or not changed.strip():
        return

    try:
        with open(MANIFEST, encoding="utf-8") as f:
            head_ver = version(f.read())
    except OSError:
        head_ver = ""
    base_ver = version(git("show", f"{BASE}:{MANIFEST}"))
    if head_ver and head_ver != base_ver:
        return

    files = "\n".join(f"  - {line}" for line in changed.splitlines())
    msg = (f"⚠️  Plugin version not bumped. Shipped paths are committed on this branch but "
           f"plugin version is still {base_ver}:\n{files}\n"
           f"Bump \"version\" in {MANIFEST} before opening the PR so consuming repos refresh "
           f"the plugin. (CI check: plugin-version-bump)")
    json.dump({"systemMessage": msg, "suppressOutput": True}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never block the stop
