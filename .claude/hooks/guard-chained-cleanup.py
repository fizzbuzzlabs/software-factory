#!/usr/bin/env python3
"""PreToolUse guard: a git worktree or branch removal runs as its own command.

Ships with the plugin (registered in hooks.json) and is wired in this repo's
.claude/settings.json. The allow entries for cleanup (`Bash(git -C * worktree *)`,
`Bash(git -C * branch -D *)` and their bare forms) approve a command only when every
part of it matches one. Chain a removal with anything else (`cd <repo>; git worktree
remove <path> && git branch -D <branch> && git branch`) and the unmatched parts send
the whole command to auto mode's classifier, which refuses it as destructive. The
dispatcher then skips a ticket it had already checked was safe to clean up.

So a Bash call that holds a removal (`git worktree remove`, `git worktree prune`,
`git branch -d` / `-D` / `--delete`) and anything else, joined by an unquoted
`;` `&&` `||` `|` `&` or newline, is denied with a message telling the model to
run each step as its own call. The hook never runs or splits the command itself,
and never approves anything: the allow list and the classifier still decide each
single command. A lone removal, and every chain without one, is untouched.

Applies to every agent and the main session. Fail-open: anything it can't parse
gets no decision.
"""
import json
import os
import shlex
import sys

# git global options that take a separate value (`git -C <repo> ...`).
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}

MESSAGE = (
    "Blocked before it ran: this chains `{what}` with other commands. The allow list "
    "approves a worktree or branch removal only as a command of its own; chained, it goes "
    "to auto mode's classifier, which refuses it. Run each step you need as its own Bash "
    "call, naming the repo with -C, such as `git -C <repo> worktree remove <path>` or "
    "`git -C <repo> branch -D <branch>`. No cd, ;, &&, || or |."
)


def segments(cmd):
    """Split cmd on unquoted command separators: ; && || | & and newline.

    Quote- and escape-aware, so a separator inside a commit message or regex stays put.
    `>&` / `&>` are redirects, not separators, and a backslash-newline joins lines.
    """
    parts, cur, quote, i = [], [], None, 0
    while i < len(cmd):
        c, nxt = cmd[i], cmd[i + 1:i + 2]
        if quote == "'":
            if c == "'":
                quote = None
            cur.append(c)
        elif c == "\\":
            if nxt != "\n":
                cur.append(cmd[i:i + 2])
            i += 2
            continue
        elif quote == '"':
            if c == '"':
                quote = None
            cur.append(c)
        elif c in "'\"":
            quote = c
            cur.append(c)
        elif c == "&" and (nxt == ">" or (cur and cur[-1] == ">")):
            cur.append(c)  # &> or >& redirect
        elif c in ";&|\n":
            parts.append("".join(cur))
            cur = []
            if nxt == c and c in "&|":
                i += 1  # && or ||
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def removal(segment):
    """Return 'git worktree remove' etc. when segment is a git worktree / branch removal."""
    try:
        argv = shlex.split(segment)
    except ValueError:
        return None
    while argv and argv[0] in ("(", "{", "!"):
        argv = argv[1:]
    if argv and argv[0].startswith("("):
        argv[0] = argv[0][1:]
    while argv and "=" in argv[0] and not argv[0].startswith("-"):
        argv = argv[1:]  # VAR=value prefix
    if not argv or os.path.basename(argv[0]) != "git":
        return None
    args = argv[1:]
    while args and args[0].startswith("-"):
        opt = args.pop(0)
        if opt in GIT_VALUE_OPTS and args:
            args.pop(0)
    if not args:
        return None
    sub, rest = args[0], args[1:]
    if sub == "worktree":
        action = next((a for a in rest if not a.startswith("-")), None)
        if action in ("remove", "prune"):
            return f"git worktree {action}"
    if sub == "branch":
        for a in rest:
            if a == "--delete" or (a.startswith("-") and not a.startswith("--") and set(a[1:]) & {"d", "D"}):
                return "git branch -D"
    return None


def check(cmd):
    """Return the deny reason for cmd, or None to let it through."""
    parts = segments(cmd)
    if len(parts) < 2:
        return None
    what = next((r for r in map(removal, parts) if r), None)
    return MESSAGE.format(what=what) if what else None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    reason = check((data.get("tool_input") or {}).get("command") or "")
    if reason:
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open: no decision
