#!/usr/bin/env python3
"""Tests for guard-chained-cleanup.py. Not a hook; nothing registers it.

  python3 -I -B -m unittest discover -s .claude/hooks -p 'test_*.py'
"""
import importlib.util
import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-chained-cleanup.py")
_spec = importlib.util.spec_from_file_location("guard_chained_cleanup", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

ALLOWED = [
    # A removal on its own, in every form the allow list names.
    "git -C /repo worktree remove /repo/.claude/worktrees/agent-a1",
    "git worktree remove .claude/worktrees/agent-a1",
    "git -C /repo worktree remove --force /repo/.claude/worktrees/agent-a1",
    "git -C /repo worktree prune",
    "git -C /repo branch -D acme/acm-45-add-a-privacy-page",
    "git branch -d feature",
    "git -C /repo branch --delete feature",
    # A redirect isn't a chain.
    "git -C /repo worktree remove /x 2>&1",
    "git -C /repo branch -D x &>/dev/null",
    # Chains with no removal are none of this hook's business.
    "npm install && npm test",
    "git -C /repo worktree list && git -C /repo branch",
    "git worktree add /x -b b origin/main && git -C /x status",
    "cd /repo; git status",
    "git log --oneline | head",
    # A separator inside quotes, or escaped, stays in one command.
    'git commit -m "cleanup: git worktree remove x && git branch -D y"',
    "git commit -m 'git branch -D x; git worktree prune'",
    "grep -n 'worktree remove\\|branch -D' run-stage.md",
    "echo a\\;b",
    # A lone branch listing or rename isn't a removal.
    "git branch -a",
    "git branch -M main",
    "git branch --list 'acme/*'",
    "",
]

DENIED = [
    # The command from a dispatcher run that failed on it.
    "cd /repo; git worktree remove .claude/worktrees/agent-e5f6a7b8 && git branch -D acme/acm-45-add-a-privacy-page && git worktree prune && git worktree list && git branch",
    "git -C /repo worktree remove /x && git -C /repo branch -D b",
    "cd /repo && git worktree remove /x",
    "git -C /repo worktree prune; git -C /repo worktree list",
    "git -C /repo branch -D b || true",
    "git -C /repo branch -D b | cat",
    "git -C /repo worktree remove /x\ngit -C /repo branch -D b",
    "(cd /repo && git branch -d b)",
    "git -C /repo branch --delete b; echo done",
    "git -C /repo branch -Df b && git -C /repo worktree list",
    "git status & git -C /repo worktree remove /x",
    "GIT_TRACE=1 git -C /repo branch -D b && echo ok",
    "/usr/bin/git -C /repo worktree remove /x && echo ok",
]


class Check(unittest.TestCase):
    def test_allowed(self):
        for cmd in ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertIsNone(guard.check(cmd))

    def test_denied(self):
        for cmd in DENIED:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(guard.check(cmd))

    def test_message_names_the_removal(self):
        self.assertIn("`git branch -D`", guard.check("cd /r && git branch -D b"))
        self.assertIn("`git worktree prune`", guard.check("git worktree prune; ls"))


class Hook(unittest.TestCase):
    def run_hook(self, payload):
        out = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(payload),
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)["hookSpecificOutput"] if out else None

    def bash(self, command, agent_type=None):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
        if agent_type:
            payload["agent_type"] = agent_type
        return self.run_hook(payload)

    def test_chained_removal_denied_in_main_session(self):
        out = self.bash("cd /r; git worktree remove /x && git branch -D b")
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("own Bash call", out["permissionDecisionReason"])

    def test_chained_removal_denied_in_a_worker(self):
        out = self.bash("git -C /r branch -D b && ls", agent_type="software-factory:dev")
        self.assertEqual(out["permissionDecision"], "deny")

    def test_single_removal_untouched(self):
        self.assertIsNone(self.bash("git -C /r worktree remove /x"))

    def test_other_tools_untouched(self):
        self.assertIsNone(self.run_hook({"tool_name": "Read", "tool_input": {"file_path": "/x"}}))

    def test_garbage_input_fails_open(self):
        out = subprocess.run([sys.executable, "-I", HOOK], input="not json",
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
