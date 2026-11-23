#!/usr/bin/env python3
"""PreToolUse guard: writes to .claude/skills/** and .claude/agents/** go through a meta-* skill.

Registered only in this repo's .claude/settings.json; it doesn't ship in hooks.json.

Trust model: the only input trusted is the harness-supplied transcript. A meta-* Skill
tool_use near the end of this session's transcript, or of one of its subagent
transcripts, authorizes the write. Nothing agent-writable is consulted: the agent can't
forge a Skill tool_use without invoking Skill.

Coverage: Edit, Write and MultiEdit by file_path, and Bash, so `printf >file` or
`sed -i` can't slip past. A Bash command is tokenized (quote-aware) and denied only when
a protected path is the target of a write: a redirect destination, or an argument to a
mutating command. A read never matches, even when the same line redirects elsewhere
(`grep x .claude/skills > /tmp/out`). Heredoc bodies are dropped first, since they're
data, and `bash -c '...'` is re-analyzed one level deep. A base64'd payload or a
`python -c` write is out of reach: this raises the cost of an accidental write, it
doesn't stop a determined one.

Scope: a path is protected only when it resolves under the project's .claude/skills or
.claude/agents. A worktree at <repo>/.claude/worktrees/<name> also protects <repo>'s
copy, so a worktree session can't reach up and edit it.

Decisions: an authorized write gets an explicit `allow`. Silence would fall through to
the permission system, whose built-in ask on .claude/** ignores Edit/Write allow rules
and parks an unattended cloud session waiting on a human. An unauthorized write gets
`deny`. Anything else, including an unexpected error, gets no decision.
"""
import glob
import json
import os
import re
import shlex
import sys
from collections import deque

META_SKILLS = {
    "meta-create-agent", "meta-update-agent", "meta-create-skill",
    "meta-update-skill", "meta-tighten", "meta-add-mcp-server",
}
# The same skills loaded through the installed plugin are named <plugin>:<skill>.
META_SKILLS |= {"software-factory:" + s for s in META_SKILLS}
DEFAULT_WINDOW_LINES = 60

# Commands that write their non-flag path arguments.
MUTATORS = {"cp", "mv", "rm", "install", "truncate", "dd", "ln", "tee", "mkdir", "rmdir",
            "touch", "chmod", "chown", "shred", "unlink"}
# Per editor: the short flags that mean in-place, and the short flags whose argument is
# the rest of the cluster (so `perl -Ilib` isn't read as -i).
IN_PLACE_EDITORS = {
    "sed": ("iI", "efl"),
    "perl": ("i", "eEMmIxCdDF"),
    "ruby": ("i", "eEIrCxKFW"),
}
GIT_WRITES = {"mv", "rm", "restore", "checkout", "apply"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}

# An unquoted newline ends a command, like `;`, so it's punctuation, not whitespace.
PUNCTUATION = "();<>|&\n"
# Longest first, so a run of punctuation splits into the operators bash would read.
OPERATORS = sorted(
    ["&>>", "<<<", ";;&", ">>", ">|", ">&", "&>", "<<", "<&", "<>", "&&", "||", "|&",
     ";;", ";&", ">", "<", "|", "&", ";", "(", ")", "\n"],
    key=len, reverse=True)
WRITE_REDIRECTS = {">", ">>", ">|", ">&", "&>", "&>>"}
READ_REDIRECTS = {"<", "<<", "<<<", "<&", "<>"}  # the next word is a source or heredoc delimiter
SEPARATORS = set(OPERATORS) - WRITE_REDIRECTS - READ_REDIRECTS

SPACE = " \t\n\r\f\v"
HEREDOC = re.compile(r"<<-?[" + SPACE + r"]*['\"]?([A-Za-z_][A-Za-z0-9_]*)")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
FD = re.compile(r"[0-9]+")

DENY_REASON = (
    "Writes to .claude/skills/** and .claude/agents/** must go through a meta-* skill: "
    "meta-create-agent / meta-update-agent (agent defs), meta-create-skill / "
    "meta-update-skill / meta-tighten (skills, conventions, agents), or meta-add-mcp-server "
    "(MCP wiring). No authorizing meta-* Skill invocation was found in this session's "
    "transcript, so this edit is not authorized — invoke the right /meta-* skill and make "
    "the change inside that flow. (Blocked {tool} write to: {target})"
)
ALLOW_REASON = ("Protected-path write authorized by an in-window meta-* Skill invocation "
                "in this session's transcript.")


# ------------------------------------------------------------------ path scoping

def normalize(path, cwd):
    """Lexically resolve path against cwd (it need not exist), folding `.` and `..`."""
    if not path.startswith("/"):
        path = cwd + "/" + path
    out = []
    for seg in path.split("/"):
        if seg == "..":
            if out:
                out.pop()
        elif seg not in ("", "."):
            out.append(seg)
    return "/" + "/".join(out)


class Scope:
    def __init__(self, project, cwd):
        self.cwd = cwd
        repos = [project]
        marker = project.find("/.claude/worktrees/")
        if marker > 0:
            repos.append(project[:marker])
        self.roots = [normalize(os.path.join(r, ".claude", d), cwd)
                      for r in repos for d in ("skills", "agents")]

    def protects(self, path):
        p = normalize(path, self.cwd)
        return any(p == r or p.startswith(r + "/") for r in self.roots)


# ----------------------------------------------------------------- authorization

def window_lines():
    try:
        return abs(int(os.environ.get("META_AUTH_WINDOW_LINES") or DEFAULT_WINDOW_LINES))
    except ValueError:
        return 0


def has_meta_call(node):
    if isinstance(node, dict):
        skill = node.get("input")
        skill = skill.get("skill") if isinstance(skill, dict) else None
        if (node.get("type") == "tool_use" and node.get("name") == "Skill"
                and isinstance(skill, str) and skill in META_SKILLS):
            return True
        return any(has_meta_call(v) for v in node.values())
    if isinstance(node, list):
        return any(has_meta_call(v) for v in node)
    return False


def scan(path):
    """True when the tail of one transcript holds a meta-* Skill call.

    Only the tail counts: a genuine meta flow edits right after its Skill call, so a
    stale call earlier in a long session doesn't authorize.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            tail = deque(f, maxlen=window_lines())
    except (OSError, ValueError):
        return False
    for line in tail:
        if not line.strip():
            continue
        try:
            if has_meta_call(json.loads(line)):
                return True
        except (ValueError, RecursionError):
            continue
    return False


def authorized(transcript):
    """Workers log Skill calls to <session>/subagents/*.jsonl, not the <session>.jsonl
    handed here, so scan both or a meta flow inside a worker fails closed."""
    if not transcript:
        return False
    if scan(transcript):
        return True
    if transcript.endswith(".jsonl"):
        pattern = os.path.join(glob.escape(transcript[:-len(".jsonl")]), "subagents", "*.jsonl")
        return any(scan(sub) for sub in sorted(glob.glob(pattern)))
    return False


# --------------------------------------------------------------- bash inspection

def strip_heredocs(command):
    """Drop heredoc bodies: `git commit -F - <<EOF` quoting `echo x > .claude/agents/a.md`
    is a message, not a write. Terminators may be indented under `<<-`; a `<<<`
    herestring is masked so it isn't read as a heredoc."""
    kept, pending = [], []
    for line in command.split("\n"):
        if pending:
            if line == pending[0] or line.lstrip(SPACE) == pending[0]:
                pending.pop(0)
            continue
        kept.append(line)
        pending += HEREDOC.findall(line.replace("<<<", "\x01"))
    return "\n".join(kept)


def split_operators(run):
    ops = []
    while run:
        op = next(o for o in OPERATORS if run.startswith(o))
        ops.append(op)
        run = run[len(op):]
    return ops


def tokenize(command):
    """Shell words and operators.

    A dangling quote is closed and a trailing backslash dropped rather than failing:
    the shell still runs every line before the one it can't parse, so a write there
    must still be seen. A backslash-newline joins two lines into one command.
    """
    command = command.replace("\\\n", " ")
    for _ in range(3):
        lex = shlex.shlex(command, posix=True, punctuation_chars=PUNCTUATION)
        lex.whitespace = SPACE.replace("\n", "")
        lex.whitespace_split = True
        lex.commenters = ""
        try:
            words = [tok for tok in lex if tok]
            break
        except ValueError:
            command = command + lex.state if lex.state in ("'", '"') else command[:-1]
    else:
        return []
    tokens = []
    for w in words:
        tokens += split_operators(w) if all(c in PUNCTUATION for c in w) else [w]
    return tokens


def protected_arg(args, scope):
    """The first non-flag argument naming a protected path; `dd of=X` is unwrapped."""
    for a in args:
        if a.startswith("-"):
            continue
        path = a[len("of="):] if a.startswith("of=") else a
        if scope.protects(path):
            return path
    return None


def edits_in_place(arg, in_place, takes_rest):
    """True when one argument turns on in-place editing: `--in-place[=SUF]`, or an
    in-place letter anywhere in a short-flag cluster (`-pi`, `-Ei`, `-0pi.bak`) before a
    flag that swallows the rest of the cluster as its argument."""
    if arg.startswith("--"):
        return arg == "--in-place" or arg.startswith("--in-place=")
    if not arg.startswith("-"):
        return False
    for c in arg[1:]:
        if c in in_place:
            return True
        if c in takes_rest:
            return False
    return False


def command_target(words, scope, depth):
    if not words:
        return None
    cmd, rest = words[0], words[1:]
    while rest and ASSIGNMENT.match(cmd):
        cmd, rest = rest[0], rest[1:]
    cmd = cmd.rsplit("/", 1)[-1]
    if cmd in MUTATORS:
        return protected_arg(rest, scope)
    if cmd in IN_PLACE_EDITORS:
        if any(edits_in_place(a, *IN_PLACE_EDITORS[cmd]) for a in rest):
            return protected_arg(rest, scope)
    elif cmd == "git":
        if rest and rest[0] in GIT_WRITES:
            return protected_arg(rest[1:], scope)
    elif cmd in SHELLS and depth == 0:
        for flag, script in zip(rest, rest[1:]):
            hit = flag == "-c" and write_target(script, scope, depth + 1)
            if hit:
                return hit
    return None


def write_target(command, scope, depth=0):
    """The protected path command writes, or None."""
    tokens = tokenize(strip_heredocs(command))
    words, i = [], 0
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if t in WRITE_REDIRECTS:
            if nxt is not None and scope.protects(nxt):
                return nxt
            i += 2
        elif t in READ_REDIRECTS:
            i += 2
        elif t in SEPARATORS:
            hit = command_target(words, scope, depth)
            if hit:
                return hit
            words, i = [], i + 1
        else:
            if not (FD.fullmatch(t) and nxt in WRITE_REDIRECTS | READ_REDIRECTS):
                words.append(t)  # `2>` arrives as an fd word, then the operator
            i += 1
    return command_target(words, scope, depth)


# ---------------------------------------------------------------------- dispatch

def text(value):
    return value if isinstance(value, str) else ""


def decide(decision, reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    tool = data.get("tool_name")
    tool_input = data.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    cwd = text(data.get("cwd")) or os.getcwd()
    scope = Scope(os.environ.get("CLAUDE_PROJECT_DIR") or cwd, cwd)

    if tool in ("Edit", "Write", "MultiEdit"):
        path = text(tool_input.get("file_path"))
        target = path if path and scope.protects(path) else None
    elif tool == "Bash":
        command = text(tool_input.get("command"))
        target = write_target(command, scope) if command else None
    else:
        return

    if not target:
        return
    if authorized(text(data.get("transcript_path"))):
        decide("allow", ALLOW_REASON)
    else:
        decide("deny", DENY_REASON.format(tool=tool, target=target[:140]))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open: no decision
