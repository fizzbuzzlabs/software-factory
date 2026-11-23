#!/usr/bin/env python3
"""PreToolUse guard: never print a secret into the transcript.

Ships with the plugin (registered in hooks.json), so it runs in every repo that
enables software-factory. Denies a tool call that would echo a secret's value:

  Bash  printenv / echo / printf of a secret-named var; a bare env / printenv /
        set / export / declare -p dump of the whole environment; a reader
        (cat, grep, head, sed, ...) on a .env file or /proc/*/environ; inline
        interpreter code (python -c, node -e, ...) that prints a secret env var.
        Recurses into $(...), backticks, and `bash -c '...'`.
  Read  a .env file or /proc/*/environ.
  Grep  content-mode search of a .env file.

A secret-named var is any name containing KEY, TOKEN, SECRET, PASSWORD/PASSWD,
CREDENTIAL, or PRIVATE (case-insensitive). .env.example / .sample / .template /
.dist are templates, not secrets, and stay readable. Non-printing uses stay
allowed: `test -n "$X"`, `${X:+x}`, `${#X}`, passing "$X" to curl, sourcing .env,
`grep -q` / `-c` / `-l` on a .env.

Not a sandbox: a script file that prints os.environ, or a base64'd payload, is
out of reach. This stops the habitual `printenv API_KEY` check, not a determined
leak. Fail-open: any parse error or unexpected input yields no decision.
"""
import json
import os
import re
import sys

SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSW(?:OR)?D|CREDENTIAL|PRIVATE", re.I)
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
DOTENV = re.compile(r"^\.env(?:rc)?(?:\..+)?$")
DOTENV_TEMPLATE = re.compile(r"\.(?:example|sample|template|dist)$")
PROC_ENVIRON = re.compile(r"^/proc/[^/]+(?:/task/[^/]+)?/environ$")

PRINTERS = {"echo", "printf", "print"}
READERS = {
    "cat", "tac", "nl", "head", "tail", "less", "more", "bat", "batcat",
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "awk", "gawk", "sed", "cut",
    "sort", "uniq", "strings", "xxd", "od", "hexdump", "base64", "diff", "column",
    "paste", "jq", "yq", "tr", "fold", "fmt", "pr",
}
GREP_FAMILY = {"grep", "egrep", "fgrep", "rg", "ag", "ack"}
WRAPPERS = {"command", "builtin", "exec", "nohup", "time", "sudo", "doas", "xargs", "timeout", "nice"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
INTERPRETERS = {"python", "python3", "python2", "node", "nodejs", "deno", "bun", "ruby", "perl", "php"}
CODE_FLAGS = {"-c", "-e", "-E", "-p", "-r", "--eval", "--print", "-pe", "-ne", "-le"}
ENV_ACCESS = re.compile(r"os\.environ|os\.getenv|getenv\s*\(|process\.env|Deno\.env|Bun\.env|\bENV\s*[\[.]|\$ENV\s*\{|\$_ENV|\$_SERVER")
CODE_PRINTS = re.compile(r"\bprint|console\.\w+|\bputs\b|\bp\s|stdout|\becho\b|\bsay\b|\bpp\b|var_dump")
ENV_DUMP = re.compile(r"\b(?:print\w*|console\.\w+|puts|pp|p|dump)\s*\(?\s*(?:dict\s*\(\s*|JSON\.stringify\s*\(\s*)?(?:os\.environ|process\.env|ENV|%ENV|\$_ENV)\s*\)?\s*\)?\s*(?:$|[;,)\n])")

SAFE_IDIOM = (
    'Check a secret is set without printing it: `test -n "$NAME"` (exit 0 = set) '
    'or `[ -n "${NAME:+x}" ]`. Never printenv / echo / cat a secret or a .env file '
    "- its value lands in the run transcript. If a key you need is missing, report "
    "it as a provisioning gap (blocked, naming the variable) instead of inspecting it."
)


def deny(why):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Blocked: {why}. {SAFE_IDIOM}",
        }
    }, sys.stdout)
    sys.exit(0)


def is_secret_file(path):
    if not path:
        return False
    path = path.strip()
    if PROC_ENVIRON.match(path):
        return True
    base = os.path.basename(path.rstrip("/"))
    return bool(DOTENV.match(base)) and not DOTENV_TEMPLATE.search(base)


# ------------------------------------------------------------------ tokenizer

def strip_heredocs(s):
    """Drop heredoc bodies: they are data (commit messages, PR bodies), not commands."""
    out, pending = [], []
    for line in s.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        masked = line.replace("<<<", "\x01")
        pending += re.findall(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)", masked)
    return "\n".join(out)


def _matching_paren(s, i):
    """Index of the `)` closing the `(` at s[i] (quote-aware enough for $(...))."""
    depth, q = 0, ""
    while i < len(s):
        c = s[i]
        if q:
            if c == q:
                q = ""
            elif c == "\\" and q == '"':
                i += 1
        elif c in "'\"":
            q = c
        elif c == "\\":
            i += 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s)


class Word:
    __slots__ = ("text", "expands")

    def __init__(self):
        self.text = ""
        self.expands = []  # var names whose VALUE this word expands to


def _read_expansion(s, i, word):
    """At s[i] == '$' (unquoted or in double quotes). Returns the new index."""
    nxt = s[i + 1] if i + 1 < len(s) else ""
    if nxt == "{":
        close = s.find("}", i + 2)
        if close == -1:
            word.text += s[i:]
            return len(s)
        body = s[i + 2:close]
        word.text += s[i:close + 1]
        if body.startswith(("#", "!")):          # ${#X} length / ${!X} indirection
            return close + 1
        m = NAME.match(body)
        if m:
            op = body[m.end():]
            if not op.startswith((":+", "+")):   # ${X:+x} never yields X's value
                word.expands.append(m.group())
        return close + 1
    m = NAME.match(s, i + 1)
    if m:
        word.text += s[i:m.end()]
        word.expands.append(m.group())
        return m.end()
    word.text += "$"
    return i + 1


def tokenize(s, subs):
    """Split into tokens: Word objects and operator strings. Command-substitution
    bodies are appended to `subs` for separate analysis."""
    toks, word, i, n = [], None, 0, len(s)

    def cur():
        nonlocal word
        if word is None:
            word = Word()
        return word

    def flush():
        nonlocal word
        if word is not None:
            toks.append(word)
            word = None

    while i < n:
        c = s[i]
        if c in " \t":
            flush()
            i += 1
        elif c == "\\":
            if i + 1 < n and s[i + 1] == "\n":
                i += 2
                continue
            cur().text += s[i + 1:i + 2]
            i += 2
        elif c == "'":
            close = s.find("'", i + 1)
            close = n if close == -1 else close
            cur().text += s[i + 1:close]
            i = close + 1
        elif c == '"':
            i += 1
            w = cur()
            while i < n and s[i] != '"':
                if s[i] == "\\" and i + 1 < n:
                    w.text += s[i + 1]
                    i += 2
                elif s[i:i + 2] == "$(":
                    end = _matching_paren(s, i + 1)
                    subs.append(s[i + 2:end])
                    w.text += "\x02"
                    i = end + 1
                elif s[i] == "`":
                    end = s.find("`", i + 1)
                    end = n if end == -1 else end
                    subs.append(s[i + 1:end])
                    w.text += "\x02"
                    i = end + 1
                elif s[i] == "$":
                    i = _read_expansion(s, i, w)
                else:
                    w.text += s[i]
                    i += 1
            i += 1
        elif s.startswith("$(", i):
            end = _matching_paren(s, i + 1)
            subs.append(s[i + 2:end])
            cur().text += "\x02"
            i = end + 1
        elif c == "`":
            end = s.find("`", i + 1)
            end = n if end == -1 else end
            subs.append(s[i + 1:end])
            cur().text += "\x02"
            i = end + 1
        elif c == "$":
            i = _read_expansion(s, i, cur())
        elif c == "#" and word is None:
            nl = s.find("\n", i)
            i = n if nl == -1 else nl
        elif c in "\n;&|()<>":
            flush()
            for op in ("<<<", "&&", "||", ">>", "<<", "&>", ">&", "<&"):
                if s.startswith(op, i):
                    break
            else:
                op = c
            toks.append(op)
            i += len(op)
        else:
            cur().text += c
            i += 1
    flush()
    return toks


# ------------------------------------------------------------------- analysis

def secret_expansions(words):
    return [v for w in words for v in w.expands if SECRET_NAME.search(v)]


def check_interpreter_code(code):
    if not ENV_ACCESS.search(code):
        return None
    if ENV_DUMP.search(code):
        return "inline code prints the whole environment"
    if CODE_PRINTS.search(code):
        for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", code):
            if m.group().isupper() and SECRET_NAME.search(m.group()):
                return f"inline code prints the secret env var {m.group()}"
    return None


def check_simple(words, herestrings, depth):
    """One simple command (a pipeline stage). Returns a reason or None."""
    args = list(words)
    while args and ASSIGN.match(args[0].text):
        args.pop(0)
    while args and args[0].text in WRAPPERS:
        args.pop(0)
        # Wrapper flags and `timeout 5` / `nice -n 10` operands.
        while args and (args[0].text.startswith("-") or re.match(r"^\d+[smhd]?$", args[0].text)):
            args.pop(0)
    if not args:
        return None
    cmd = os.path.basename(args[0].text)
    rest = args[1:]
    texts = [w.text for w in rest]

    if cmd == "env":
        # `env [-i] [-u NAME] [NAME=val]... [cmd ...]` — dump only when no cmd follows.
        j = 0
        while j < len(rest):
            t = texts[j]
            if t in ("-u", "--unset", "-C", "--chdir", "-S", "--split-string"):
                j += 2
            elif t.startswith("-") or ASSIGN.match(t):
                j += 1
            else:
                return check_simple(rest[j:], herestrings, depth)
        return "`env` with no command dumps every environment variable, secrets included"

    if cmd == "printenv":
        names = [t for t in texts if not t.startswith("-")]
        if not names:
            return "bare `printenv` dumps every environment variable, secrets included"
        hit = [t for t in names if SECRET_NAME.search(t)]
        if hit:
            return f"`printenv {hit[0]}` prints a secret's value"
        return None

    if cmd == "set" and not texts:
        return "bare `set` dumps every shell variable, secrets included"
    if cmd == "export" and all(t == "-p" for t in texts):
        return "`export -p` dumps every exported variable, secrets included"
    if cmd in ("declare", "typeset"):
        flags = [t for t in texts if t.startswith("-")]
        names = [t for t in texts if not t.startswith("-")]
        if any("p" in f for f in flags):
            if not names:
                return f"`{cmd} -p` dumps every variable, secrets included"
            hit = [t for t in names if SECRET_NAME.search(t)]
            if hit:
                return f"`{cmd} -p {hit[0]}` prints a secret's value"

    if cmd in PRINTERS:
        hit = secret_expansions(rest)
        if hit:
            return f"`{cmd}` of ${hit[0]} prints a secret's value"

    if cmd in READERS or cmd in PRINTERS:
        hit = secret_expansions(herestrings)
        if hit:
            return f"feeding ${hit[0]} to `{cmd}` prints a secret's value"

    if cmd in READERS:
        quiet = cmd in GREP_FAMILY and any(
            t in ("--quiet", "--silent", "--count", "--files-with-matches", "--files-without-match")
            or (re.match(r"^-[A-Za-z]+$", t) and re.search(r"[qclL]", t))
            for t in texts
        )
        if not quiet:
            for t in texts:
                for part in t.split("="):          # --file=.env, of=.env
                    if is_secret_file(part):
                        return f"`{cmd} {t}` prints a secrets file"

    if cmd in INTERPRETERS:
        for j, t in enumerate(texts):
            if t in CODE_FLAGS and j + 1 < len(texts):
                reason = check_interpreter_code(texts[j + 1])
                if reason:
                    return reason

    if cmd in SHELLS and depth < 3:
        for j, t in enumerate(texts):
            if t == "-c" and j + 1 < len(texts):
                return analyze(texts[j + 1], depth + 1)
    return None


def analyze(cmd, depth=0):
    subs = []
    toks = tokenize(strip_heredocs(cmd), subs)
    words, here, redirect, stdin_file = [], [], None, None
    for t in toks + [";"]:
        if isinstance(t, Word):
            if redirect == "<<<":
                here.append(t)
            elif redirect == "<" and is_secret_file(t.text):
                stdin_file = t.text
            elif redirect is None:
                words.append(t)
            redirect = None
            continue
        if t in ("<<<", "<", ">", ">>", "&>", "<<", "<&", ">&"):
            redirect = t                       # its operand is not an argument
        elif t in ("\n", ";", "&", "&&", "|", "||", "(", ")"):
            if words or here:
                reason = check_simple(words, here, depth)
                if reason:
                    return reason
                cmd = next((os.path.basename(w.text) for w in words if not ASSIGN.match(w.text)), "")
                if stdin_file and cmd in READERS | PRINTERS:
                    return f"`{cmd} < {stdin_file}` prints a secrets file"
            words, here, redirect, stdin_file = [], [], None, None
    if depth < 3:
        for sub in subs:
            reason = analyze(sub, depth + 1)
            if reason:
                return reason
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    if tool == "Bash":
        reason = analyze(ti.get("command") or "")
        if reason:
            deny(reason)
    elif tool == "Read":
        if is_secret_file(ti.get("file_path")):
            deny(f"reading {os.path.basename(ti['file_path'])} prints a secrets file")
    elif tool == "Grep":
        if ti.get("output_mode") == "content" and (
            is_secret_file(ti.get("path")) or is_secret_file((ti.get("glob") or "").replace("*", ""))
        ):
            deny("a content-mode Grep of a .env file prints its secrets")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        pass  # fail open
