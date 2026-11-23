#!/usr/bin/env python3
"""Tests for guard-readonly-search.py. Not a hook; nothing registers it.

  python3 -I -B -m unittest discover -s .claude/hooks -p 'test_*.py'
"""
import importlib.util
import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-readonly-search.py")
_spec = importlib.util.spec_from_file_location("guard_readonly_search", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

ALLOWED = [
    # Quoted-regex alternation and grouping is one grep.
    'grep -nE "(foo|bar)\\(" src',
    "grep -rnE '^(import|export) .*from' src",
    'grep -nE "^(export )?(async )?function (run|stop)$" src/main.ts',
    'grep -nE "foo$|bar$" src',
    'rg -n "a|b" .',
    # Escaped / quoted find grouping with -o is one find.
    "find . \\( -name '*.ts' -o -name '*.tsx' \\) -not -path '*/node_modules/*'",
    "find src '(' -name a -o -name b ')'",
    # An escaped quote inside double quotes doesn't end the string.
    'grep -n "say \\"hi|bye\\"" src',
    "grep -n foo\\|bar src",
    # Quoted or escaped braces, and braces with no , or .., aren't brace expansion.
    "grep -nE 'a{2,3}' src",
    'rg -n "x{1,2}|{a..b}" .',
    "find . -name '{a,b}'",
    "grep -n \\{a,b\\} src",
    "grep -nE a{2} src",
    "ls -la",
    "pwd",
    "git log --oneline -5",
    "git grep -n 'a|b'",
]

DENIED = [
    "grep foo src | head",
    "grep foo src; rm -rf src",
    "grep foo src && ls",
    "grep foo src || ls",
    "grep foo src > out.txt",
    "cat < /etc/passwd",
    "(grep foo src)",
    "grep foo src &",
    "grep foo\nrm -rf src",
    "grep $(whoami) src",
    'grep "$(whoami)" src',
    'grep "`whoami`" src',
    "grep `whoami` src",
    'grep "$HOME" src',
    'grep "${x:=y}" src',
    'grep "$[1+1]" src',
    "grep $HOME src",
    "find . -name x $'-delete'",
    "find . -name x \\\n-delete",
    'find . "-del\\\nete"',
    "find . -name x \\-delete",
    # Unquoted brace expansion builds a write / exec flag the argv check never sees.
    "find . {-delete,}",
    "find . -name x {-exec,} rm {} +",
    'find . -name x {"-delete",}',
    "find . {-dele,-delete}",
    "cat {1..3}",
    "find . \\( -name a -o -name b \\) -exec rm {} +",
    "find . -delete",
    "rg --pre=cat foo",
    "git push",
    "git log --output=x",
    "rm -rf src",
    "/bin/grep foo",
    "X=1 grep foo",
    "grep 'unbalanced",
    "",
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


class Hook(unittest.TestCase):
    def run_hook(self, agent_type, command):
        payload = {"tool_name": "Bash", "agent_type": agent_type, "tool_input": {"command": command}}
        out = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(payload),
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else None

    def test_guarded_agent_single_quoted_alternation_passes(self):
        self.assertIsNone(self.run_hook("software-factory:codebase-analyzer", 'grep -nE "(a|b)" src'))

    def test_guarded_agent_escaped_find_grouping_passes(self):
        cmd = "find . \\( -name a -o -name b \\)"
        self.assertIsNone(self.run_hook("codebase-locator", cmd))

    def test_guarded_agent_pipe_denied(self):
        self.assertEqual(self.run_hook("codebase-pattern-finder", "grep a src | head"), "deny")

    def test_unguarded_agent_untouched(self):
        self.assertIsNone(self.run_hook("dev", "grep a src | head"))


if __name__ == "__main__":
    unittest.main()
