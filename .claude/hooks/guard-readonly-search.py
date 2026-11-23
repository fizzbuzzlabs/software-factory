#!/usr/bin/env python3
"""PreToolUse guard: the codebase-* research agents get Bash for search only.

Ships with the plugin (registered in hooks.json) and is wired in this repo's
.claude/settings.json. Some Claude Code sessions expose no Glob / Grep / LS, so
codebase-locator, codebase-analyzer and codebase-pattern-finder hold Bash to
search with find / grep. This keeps them read-only: inside one of those agents
(the hook input's agent_type, bare or plugin-qualified as
`software-factory:codebase-locator`), a Bash call is allowed only when it is

  - one literal command: no ; & | < > ( ) or newline unless quoted or
    backslash-escaped, no backtick or backslash-newline outside single quotes,
    no $ outside quotes or starting an expansion ($x, ${, $( ...) inside
    double quotes, and no unquoted brace expansion ({a,b} or {1..3});
  - a bare command name from SEARCHERS (no path, no VAR=val prefix);
  - free of that command's write / exec flags (find -delete / -exec,
    rg --pre, git --output, ...).

Every other agent, and the main session, is untouched. Fail-closed inside a
guarded agent (an unparseable command is denied); fail-open everywhere else.
"""
import json
import shlex
import sys

GUARDED_AGENTS = {"codebase-locator", "codebase-analyzer", "codebase-pattern-finder"}

SEARCHERS = {"find", "grep", "egrep", "fgrep", "rg", "ls", "cat", "head", "tail", "wc", "stat", "pwd", "git"}
GIT_SUBCOMMANDS = {"ls-files", "grep", "log", "show", "blame"}

# Flags that make a searcher write a file or run another program.
FIND_ACTIONS = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fls", "-fprint", "-fprint0", "-fprintf"}
RG_EXEC = ("--pre",)
GIT_WRITES = ("--output", "-O", "--open-files-in-pager", "--ext-diff", "--textconv")

# After `$` inside double quotes, these (and any letter or digit) start an expansion;
# anything else, like a regex's `$"` or `$|`, leaves the `$` literal.
EXPANSION_START = set("_{([@*#?$!-")

USAGE = (
    "Your Bash is search-only: one literal find / grep / rg / ls / cat / head / tail / "
    "wc / stat / pwd command per call, or git ls-files / grep / log / show / blame. "
    "No chains, pipes, redirects, $(...), or write / exec flags."
)


def deny(why):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Blocked: {why}. {USAGE}",
        }
    }, sys.stdout)
    sys.exit(0)


def is_guarded(agent_type):
    return (agent_type or "").rsplit(":", 1)[-1] in GUARDED_AGENTS


def shell_syntax(cmd):
    """Return the first shell metacharacter that makes cmd more than one literal command.

    Tracks quoting and backslash escapes the way bash does, so a `|` or `(` inside a
    quoted regex, `find \\( ... -o ... \\)`, or a regex's `$` anchor stays one command.
    """
    quote = None
    braces = 0  # unquoted `{` still open; a `,` or `..` inside one is brace expansion
    i = 0
    while i < len(cmd):
        c, nxt = cmd[i], cmd[i + 1:i + 2]
        if quote == "'":
            if c == "'":
                quote = None
        elif c == "\\":
            if nxt == "\n":
                return "\\<newline>"  # bash joins the lines; shlex doesn't
            i += 2  # the escaped character is literal
            continue
        elif c == "`":
            return c
        elif c == "$":
            if quote is None or not nxt or nxt in EXPANSION_START or nxt.isalnum():
                return c
        elif quote == '"':
            if c == '"':
                quote = None
        elif c in "'\"":
            quote = c
        elif c in ";&|<>()\n":
            return c
        elif c == "{":
            braces += 1
        elif c == "}":
            braces = max(braces - 1, 0)
        elif braces and (c == "," or cmd[i:i + 2] == ".."):
            return "{…,…}"  # bash expands find . {-delete,} to find . -delete
        i += 1
    return None


def check(cmd):
    bad = shell_syntax(cmd)
    if bad:
        return f"`{bad}` makes this more than one literal command"
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return "the command doesn't parse (unbalanced quotes)"
    if not argv:
        return "empty command"
    name, args = argv[0], argv[1:]
    if name not in SEARCHERS:
        return f"`{name}` isn't a search command"
    if name == "find":
        hit = next((a for a in args if a in FIND_ACTIONS), None)
        if hit:
            return f"find `{hit}` writes or runs a program"
    if name == "rg":
        hit = next((a for a in args if a.startswith(RG_EXEC)), None)
        if hit:
            return f"rg `{hit}` runs a program"
    if name == "git":
        if not args or args[0] not in GIT_SUBCOMMANDS:
            return f"git `{args[0] if args else ''}` isn't a read-only search subcommand"
        hit = next((a for a in args[1:] if a.startswith(GIT_WRITES)), None)
        if hit:
            return f"git `{hit}` writes or runs a program"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Bash" or not is_guarded(data.get("agent_type")):
        return
    try:
        reason = check((data.get("tool_input") or {}).get("command") or "")
    except Exception:
        reason = "the guard couldn't analyze the command"
    if reason:
        deny(reason)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        pass  # fail open outside a guarded agent; check() already fails closed
