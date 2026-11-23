#!/usr/bin/env python3
"""Build an arm: a plugin folder holding one version of the factory, ready to load with --plugin-dir.

    build_arm.py <ref> [--name N]   the factory as committed at a git ref (branch, tag or sha)
    build_arm.py --worktree <name> [--from <path>]
                                    the factory as it is right now in this checkout, or in another one

Each arm gets two plugin folders under .arms/<name>/:
  fake-workers/   real skills and hooks, stand-in agents that run a scripted worker (dispatcher cases)
  real-workers/   real skills, hooks and agents (worker cases)
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = subprocess.run(["git", "-C", HERE, "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True, check=True).stdout.strip()
WORKERS = ["architect", "cto", "dev", "qa"]


def arm_name(ref):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", ref).strip("-")


SOURCE = REPO


def export(ref, target):
    """Write .claude/skills, .claude/agents and .claude/hooks from a ref (or a working tree) into target."""
    if ref is None:
        for part in ("skills", "agents", "hooks"):
            shutil.copytree(os.path.join(SOURCE, ".claude", part), os.path.join(target, part),
                            ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".deps-*"))
        return
    archive = subprocess.run(["git", "-C", REPO, "archive", ref, ".claude/skills", ".claude/agents",
                              ".claude/hooks"], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(target, filter="data") if sys.version_info >= (3, 12) else tar.extractall(target)
    for part in ("skills", "agents", "hooks"):
        os.rename(os.path.join(target, ".claude", part), os.path.join(target, part))
    os.rmdir(os.path.join(target, ".claude"))


def version_at(ref):
    path = "plugin/.claude-plugin/plugin.json"
    if ref is None:
        with open(os.path.join(SOURCE, path)) as handle:
            return json.load(handle)["version"]
    shown = subprocess.run(["git", "-C", REPO, "show", "%s:%s" % (ref, path)],
                           capture_output=True, text=True, check=True).stdout
    return json.loads(shown)["version"]


def stand_in(agent_text, stage, template):
    """Keep an agent's name, description and Queue config; replace everything else with the stand-in body."""
    front = re.match(r"---\n(.*?)\n---\n", agent_text, re.S)
    fields = dict(re.findall(r"^(name|description):\s*(.*)$", front.group(1), re.M))
    queue = re.search(r"^## Queue config\n.*?(?=^## |\Z)", agent_text, re.S | re.M)
    body = template.replace("{stage}", stage)
    return ("---\nname: %s\ndescription: %s\ntools: Bash\nmodel: haiku\n---\n\n%s\n%s"
            % (fields["name"], fields["description"], body, queue.group(0) if queue else ""))


def build(ref, name):
    root = os.path.join(HERE, ".arms", name)
    shutil.rmtree(root, ignore_errors=True)
    manifest = {"name": "software-factory", "version": version_at(ref),
                "description": "The software factory, built for a pipeline eval arm."}
    with open(os.path.join(HERE, "stub-agent.md")) as handle:
        template = handle.read()

    for flavour in ("fake-workers", "real-workers"):
        plugin = os.path.join(root, flavour)
        os.makedirs(os.path.join(plugin, ".claude-plugin"))
        export(ref, plugin)
        with open(os.path.join(plugin, ".claude-plugin", "plugin.json"), "w") as handle:
            json.dump(manifest, handle, indent=2)

    agents = os.path.join(root, "fake-workers", "agents")
    for stage in WORKERS:
        path = os.path.join(agents, stage + ".md")
        with open(path) as handle:
            text = handle.read()
        with open(path, "w") as handle:
            handle.write(stand_in(text, stage, template))
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ref", nargs="?", help="git ref to build from")
    parser.add_argument("--worktree", metavar="NAME", help="build from the working tree, under this arm name")
    parser.add_argument("--name", help="arm name for a ref build (default: the ref, with / turned into -)")
    parser.add_argument("--from", dest="source", metavar="PATH",
                        help="with --worktree: another checkout of the factory to build from (default: this one)")
    arguments = parser.parse_args()
    if bool(arguments.ref) == bool(arguments.worktree):
        parser.error("give a ref, or --worktree <name>")
    if arguments.source:
        global SOURCE
        SOURCE = os.path.abspath(arguments.source)
    name = arguments.worktree or arguments.name or arm_name(arguments.ref)
    print(build(None if arguments.worktree else arguments.ref, name))


if __name__ == "__main__":
    main()
