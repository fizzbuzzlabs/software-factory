#!/usr/bin/env python3
"""Tests for guard-protected-paths.py. Not a hook; nothing registers it.

  python3 -I -B -m unittest discover -s .claude/hooks -p 'test_*.py'

Each test runs the hook as a subprocess against a throwaway repo, the way the
harness does: a PreToolUse payload on stdin, CLAUDE_PROJECT_DIR in the env.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK_CMD = [sys.executable, "-I",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-protected-paths.py")]

SKILL = ".claude/skills/demo/SKILL.md"
AGENT = ".claude/agents/dev.md"

# Bash commands that write a protected path. Relative paths resolve against the repo.
WRITES = [
    f"echo x > {SKILL}",
    f"printf x >> {AGENT}",
    f'echo x > "{AGENT}"',
    f"echo x 2> {SKILL}",
    f"echo x >| {SKILL}",
    f"rm {SKILL}; echo 'unclosed",
    f"echo x > .claude/skills/../skills/demo/SKILL.md",
    f"cat <<EOF > {SKILL}\nbody\nEOF",
    f"sed -i '' 's/a/b/' {SKILL}",
    f"perl -i -pe 's/a/b/' {AGENT}",
    "rm -rf .claude/skills/demo",
    f"/bin/rm {AGENT}",
    f"cp /tmp/x {AGENT}",
    f"FOO=1 mv /tmp/x {SKILL}",
    f"dd if=/dev/zero of={AGENT}",
    f"git rm {SKILL}",
    f"git checkout -- {AGENT}",
    f"ls && touch .claude/skills/demo/new.md",
    f"tee {SKILL} < /tmp/x",
    f"echo x | tee -a {AGENT}",
    f"(cd /tmp; mkdir .claude/skills/other)",
    f"bash -c 'echo x > {SKILL}'",
    f'sh -c "rm {AGENT}"',
    f"cd /tmp\nrm {SKILL}",
    f"echo ok\n\ntouch {AGENT}",
    f"ls &&\nrm {SKILL}",
    f"bash -c 'cd /tmp\nrm {AGENT}'",
    f"rm /tmp/x \\\n  {SKILL}",
    f"perl -pi -e 's/a/b/' {SKILL}",
    f"perl -pi.bak -e 's/a/b/' {AGENT}",
    f"perl -0pi -e 's/a/b/' {SKILL}",
    f"ruby -pi -e 'x' {SKILL}",
    f"sed -Ei 's/a/b/' {SKILL}",
    f"sed -ni.bak '1p' {AGENT}",
    f"sed -I '' 's/a/b/' {SKILL}",
    f"sed --in-place=.bak 's/a/b/' {SKILL}",
]

# Commands that only read a protected path, or write somewhere else.
NON_WRITES = [
    f"cat {SKILL}",
    "ls .claude/agents",
    "find .claude/skills -name '*.md'",
    "grep -rn foo .claude/skills > /tmp/out",
    f"head -5 {AGENT} 2>&1",
    f"wc -l {SKILL} >&2",
    f"sed -n '1,5p' {SKILL}",
    f"git add {SKILL}",
    "git diff .claude/agents",
    f"cat < {SKILL}",
    f"cat <<< {SKILL}",
    f'git commit -m "note: echo x > {AGENT}"',
    f"git commit -F - <<'EOF'\nGuard: echo x > {AGENT}\nrm -rf .claude/skills\nEOF",
    f"cat <<-EOF | git commit -F -\n\techo x > {SKILL}\n\tEOF\ngit log -1",
    f"bash -c 'cat {SKILL}'",
    "echo x > /tmp/out",
    "rm -rf /tmp/elsewhere/.claude/skills",
    f'git commit -m "first line\nrm {SKILL}"',
    f"echo ok\ncat {SKILL}",
    f"sed -e 's/i/x/' {SKILL}",
    f"sed -n -e '/i/p' {AGENT}",
    f"perl -Mstrict -ne 'print' {SKILL}",
    f"perl -Ilib -ne 'print' {AGENT}",
    f"ruby -ropen-uri -e 'x' {SKILL}",
    "",
]


def skill_call(skill):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]}}


class GuardProtectedPaths(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(self.repo, ".claude", "skills", "demo"))
        self.transcript = os.path.join(self.root, "session.jsonl")
        self.log(self.transcript, {"type": "user", "message": {"content": "hi"}})

    def log(self, path, *events):
        with open(path, "a") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    def run_hook(self, tool, tool_input, project=None, cwd=None):
        project = project or self.repo
        payload = {"tool_name": tool, "tool_input": tool_input,
                   "transcript_path": self.transcript, "cwd": cwd or project}
        env = {k: v for k, v in os.environ.items() if k != "META_AUTH_WINDOW_LINES"}
        env["CLAUDE_PROJECT_DIR"] = project
        out = subprocess.run(HOOK_CMD, input=json.dumps(payload), capture_output=True,
                             text=True, env=env, cwd=self.root, check=True).stdout
        return json.loads(out)["hookSpecificOutput"] if out.strip() else None

    def decision(self, *args, **kwargs):
        out = self.run_hook(*args, **kwargs)
        return out and out["permissionDecision"]

    def edit(self, path, **kwargs):
        return self.decision("Edit", {"file_path": path, "old_string": "a", "new_string": "b"}, **kwargs)

    def bash(self, command, **kwargs):
        return self.decision("Bash", {"command": command}, **kwargs)

    # ------------------------------------------------------------ Edit / Write

    def test_unauthorized_edit_denied(self):
        out = self.run_hook("Edit", {"file_path": os.path.join(self.repo, SKILL)})
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("meta-* skill", out["permissionDecisionReason"])

    def test_authorized_edit_allowed(self):
        self.log(self.transcript, skill_call("meta-update-skill"))
        self.assertEqual(self.edit(os.path.join(self.repo, SKILL)), "allow")

    def test_every_tool_that_writes_is_guarded(self):
        for tool in ("Edit", "Write", "MultiEdit"):
            with self.subTest(tool=tool):
                self.assertEqual(self.decision(tool, {"file_path": os.path.join(self.repo, AGENT)}), "deny")

    def test_relative_path_resolves_against_cwd(self):
        self.assertEqual(self.edit(AGENT), "deny")

    def test_unprotected_edit_untouched(self):
        self.assertIsNone(self.edit(os.path.join(self.repo, "src", "app.py")))
        self.assertIsNone(self.edit(os.path.join(self.repo, ".claude", "settings.json")))

    def test_non_meta_skill_does_not_authorize(self):
        self.log(self.transcript, skill_call("workflow-implement"))
        self.assertEqual(self.edit(os.path.join(self.repo, SKILL)), "deny")

    def test_plugin_prefixed_meta_skill_authorizes(self):
        self.log(self.transcript, skill_call("software-factory:meta-update-skill"))
        self.assertEqual(self.edit(os.path.join(self.repo, SKILL)), "allow")

    def test_other_plugin_meta_skill_does_not_authorize(self):
        self.log(self.transcript, skill_call("other-plugin:meta-update-skill"))
        self.assertEqual(self.edit(os.path.join(self.repo, SKILL)), "deny")

    def test_subagent_transcript_authorizes(self):
        sub = os.path.join(self.root, "session", "subagents")
        os.makedirs(sub)
        self.log(os.path.join(sub, "agent-1.jsonl"), skill_call("meta-tighten"))
        self.assertEqual(self.edit(os.path.join(self.repo, SKILL)), "allow")

    def test_stale_authorization_denied(self):
        self.log(self.transcript, skill_call("meta-update-agent"),
                 *[{"type": "user", "message": {"content": str(i)}} for i in range(60)])
        self.assertEqual(self.edit(os.path.join(self.repo, AGENT)), "deny")

    def test_other_tools_untouched(self):
        self.assertIsNone(self.decision("Read", {"file_path": os.path.join(self.repo, SKILL)}))

    def test_garbage_input_fails_open(self):
        out = subprocess.run(HOOK_CMD, input="not json", capture_output=True, text=True,
                             cwd=self.root).stdout
        self.assertEqual(out.strip(), "")

    # -------------------------------------------------------------------- Bash

    def test_bash_writes_denied(self):
        for cmd in WRITES:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd, cwd=self.repo), "deny")

    def test_bash_absolute_write_denied(self):
        self.assertEqual(self.bash(f"cd /tmp; echo x > {self.repo}/{SKILL}"), "deny")

    def test_bash_non_writes_untouched(self):
        for cmd in NON_WRITES:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.bash(cmd, cwd=self.repo))

    def test_bash_authorized_write_allowed(self):
        self.log(self.transcript, skill_call("meta-create-skill"))
        self.assertEqual(self.bash(f"echo x > {SKILL}", cwd=self.repo), "allow")

    def test_deny_names_the_target(self):
        out = self.run_hook("Bash", {"command": f"echo x > {SKILL}"}, cwd=self.repo)
        self.assertIn(SKILL, out["permissionDecisionReason"])

    # --------------------------------------------------------------- worktrees

    def test_worktree_protects_parent_repo(self):
        wt = os.path.join(self.repo, ".claude", "worktrees", "agent-1")
        os.makedirs(wt)
        self.assertEqual(self.edit(os.path.join(self.repo, SKILL), project=wt), "deny")
        self.assertEqual(self.edit(os.path.join(wt, AGENT), project=wt), "deny")
        self.assertEqual(self.bash(f"echo x > ../../../{AGENT}", project=wt), "deny")
        self.log(self.transcript, skill_call("meta-update-agent"))
        self.assertEqual(self.edit(os.path.join(self.repo, AGENT), project=wt), "allow")

    def test_plain_repo_does_not_protect_its_parent(self):
        self.assertIsNone(self.edit(os.path.join(self.root, SKILL)))


if __name__ == "__main__":
    unittest.main()
