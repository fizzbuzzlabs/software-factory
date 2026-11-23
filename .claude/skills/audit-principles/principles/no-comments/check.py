#!/usr/bin/env python3
"""no-comments check: code and tests carry no comments, and test names carry no history ids.

Reads <dir>/config.json (source roots, excludes, test globs, allowed comment patterns, ticket keys,
how strict each rule is) and <dir>/baseline.json (known violations), where <dir> defaults to
controls/no-comments. Exit 0 when clean, 1 on any failure, 2 on a usage error.

  check.py                     fail on new violations and stale baseline entries
  check.py --base origin/main  also fail when the baseline grew compared with that ref
  check.py --write-baseline    record today's violations
  check.py --report            print every measurement as JSON (rules in any mode)

Stdlib only, Python 3.9+. Languages: ts (TypeScript and JavaScript), swift and css.
"""
import argparse
import bisect
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

DEFAULT_DIR = "controls/no-comments"
EXTENSIONS = {
    "ts": (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"),
    "swift": (".swift",),
    "css": (".css",),
}
RULES = ("comment", "history-id")
MODES = ("off", "baseline", "strict")
FIX = {
    "comment": "delete it. A why goes into a test or a name, what changed goes into the commit message",
    "history-id": "name the test, reason or file after the behavior it checks, without the id",
}
GENERATED = re.compile(r"@generated\b|\bCode generated\b.*\bDO NOT EDIT\b", re.I | re.S)
ESLINT_NEXT_LINE = re.compile(r"^eslint-disable-next-line\s+[^\s,]+\s+--\s+\S")
HISTORY_TEXT = (
    r"\bbehaviou?rs?\s*#?\s*\d+\b|\b(?:spec|design|research|contract|test-plan)\.md\b|\btest-plan\b"
    r"|\banti-behaviou?rs?\b|\btesting decisions\b|\b(?:[A-Z]\d+-)?QA[- ]?B\d+(?:-\d+)?\b"
    r"|\b(?:[A-Z]\d+-)?B\d+-\d+\b|\b(?:AMB|GAP|FGM)-\d+\b|\bQA (?:delta|case|additive)\b"
)
HISTORY_IDENT = r"[Bb]ehaviou?rs?_?\d+|QA_?B\d+|B\d+_\d+|(?:AMB|GAP|FGM)_?\d+|[Tt]estPlan"
TS_TITLE = re.compile(r"(?<![\w$.])(?:describe|it|test|suite|bench)(?:\s*\.\s*\w+)*\s*\(\s*(['\"`])((?:\\.|(?!\1)[^\\])*)\1", re.S)
SWIFT_TITLE = re.compile(r'@(?:Test|Suite)\s*\(\s*"((?:\\.|[^"\\])*)"')
SWIFT_REASON = re.compile(r"(?:\bXCTSkip(?:If|Unless)?|\bXCTExpectFailure|\bwithKnownIssue|\.disabled|\.enabled|\.bug)"
                          r"\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
SWIFT_STRING = re.compile(r'"((?:\\.|[^"\\])*)"')
SWIFT_NAME = re.compile(r"\b(?:func|class|struct|enum|actor|extension)\s+(\w+)")
SWIFT_QUOTE = re.compile(r'(#*)"')
REGEX_AFTER_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "yield", "await"}


def git(root, *args):
    try:
        out = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=True)
        return out.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def norm_path(p):
    p = p.replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def language_of(rel):
    for lang, exts in EXTENSIONS.items():
        if rel.endswith(exts):
            return lang
    return None


class Config:
    def __init__(self, cfg):
        self.roots = [norm_path(r) for r in cfg.get("roots", [])]
        if not self.roots:
            raise SystemExit("config: roots must list at least one source directory")
        self.exclude = cfg.get("exclude", [])
        self.tests = cfg.get("tests", [])
        self.allow = cfg.get("allow", [])
        self.ticket_keys = cfg.get("ticket_keys", [])
        try:
            self.allow_patterns = [re.compile(p) for p in self.allow]
        except re.error as e:
            raise SystemExit(f"config: allow has an invalid regex: {e}")
        keys = "|".join(re.escape(k) for k in self.ticket_keys)
        self.history_text = re.compile((rf"\b(?:{keys})-\d+\b|" if keys else "") + HISTORY_TEXT, re.I)
        self.history_ident = re.compile(r"(?:^|_|(?<=[a-z0-9])(?=[A-Z]))(?:"
                                        + (rf"(?i:{keys})_?\d+|" if keys else "") + HISTORY_IDENT + r")(?![a-z])")
        self.rules = {r: cfg.get("rules", {}).get(r, "strict") for r in RULES}
        for r, m in self.rules.items():
            if m not in MODES:
                raise SystemExit(f"config: rules.{r} must be one of {', '.join(MODES)}")

    def is_test(self, rel):
        return any(fnmatch.fnmatch(rel, pat) for pat in self.tests)

    def root_of(self, rel):
        for r in sorted(self.roots, key=len, reverse=True):
            if rel == r or rel.startswith(r + "/"):
                return r
        return None


def source_files(root, cfg):
    listed = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--", *cfg.roots)
    if listed is None:
        listed_files = []
        for r in cfg.roots:
            for dirpath, dirnames, filenames in os.walk(os.path.join(root, r)):
                dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git", "dist", "build")]
                for f in filenames:
                    listed_files.append(os.path.relpath(os.path.join(dirpath, f), root))
    else:
        listed_files = listed.splitlines()
    out = []
    for f in listed_files:
        f = norm_path(f)
        if language_of(f) is None or any(fnmatch.fnmatch(f, pat) for pat in cfg.exclude):
            continue
        if os.path.isfile(os.path.join(root, f)):
            out.append(f)
    return sorted(set(out))


def skip_shebang(src):
    if src.startswith("#!"):
        j = src.find("\n")
        return len(src) if j < 0 else j
    return 0


def lex_ts(src):
    """Return (start, end, kind, body) for each comment, skipping strings, templates and regex literals."""
    out = []
    n = len(src)
    i = skip_shebang(src)
    prev, prev_word = "", ""
    braces = []

    def template(i):
        while i < n:
            if src[i] == "\\":
                i += 2
            elif src[i] == "`":
                return i + 1, False
            elif src.startswith("${", i):
                return i + 2, True
            else:
                i += 1
        return n, False

    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append((i, j, "line", src[i + 2:j]))
            i = j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            body = src[i:j]
            kind = "doc" if body.startswith("/**") and not body.startswith("/**/") else "block"
            out.append((i, j, kind, body[2:-2]))
            i = j
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            i = j + 1
            prev, prev_word = "a", ""
            continue
        if c == "`":
            i, opened = template(i + 1)
            if opened:
                braces.append(True)
            prev, prev_word = "a", ""
            continue
        if c == "{":
            braces.append(False)
        elif c == "}" and braces and braces.pop():
            i, opened = template(i + 1)
            if opened:
                braces.append(True)
            prev, prev_word = "a", ""
            continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^" or prev_word in REGEX_AFTER_WORDS):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            if j < n and src[j] == "/":
                i = j + 1
                while i < n and src[i].isalpha():
                    i += 1
                prev, prev_word = "a", ""
                continue
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            prev, prev_word = "a", src[i:j]
            i = j
            continue
        prev, prev_word = c, ""
        i += 1
    return out


def swift_string(src, i, hashes):
    """Return the end of the Swift string literal whose opening quote is at i."""
    n = len(src)
    quote = '"""' if src.startswith('"""', i) else '"'
    close = quote + "#" * hashes
    escape = "\\" + "#" * hashes
    i += len(quote)
    while i < n:
        if src.startswith(escape, i):
            k = i + len(escape)
            if src[k:k + 1] != "(":
                i = k + 1
                continue
            depth, k = 1, k + 1
            while k < n and depth:
                m = SWIFT_QUOTE.match(src, k)
                if m:
                    k = swift_string(src, k + len(m.group(1)), len(m.group(1)))
                    continue
                depth += {"(": 1, ")": -1}.get(src[k], 0)
                k += 1
            i = k
            continue
        if src.startswith(close, i):
            return i + len(close)
        if src[i] == "\n" and quote == '"':
            return i
        i += 1
    return n


def lex_swift(src):
    """Return (start, end, kind, body) for each comment, skipping strings (raw and multi-line included)."""
    out = []
    n = len(src)
    i = skip_shebang(src)
    while i < n:
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            text = src[i:j]
            kind = "doc" if text.startswith("///") else "mark" if re.match(r"//\s*MARK:", text) else "line"
            out.append((i, j, kind, text[2:]))
            i = j
            continue
        if src.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            body = src[i:j]
            out.append((i, j, "doc" if body.startswith("/**") else "block", body[2:-2]))
            i = j
            continue
        m = SWIFT_QUOTE.match(src, i)
        if m:
            i = swift_string(src, i + len(m.group(1)), len(m.group(1)))
            continue
        i += 1
    return out


def lex_css(src):
    return [(m.start(), m.end(), "block", m.group(0)[2:-2])
            for m in re.finditer(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|/\*[\s\S]*?\*/', src)
            if m.group(0).startswith("/*")]


LEXERS = {"ts": lex_ts, "swift": lex_swift, "css": lex_css}


def allowed(cfg, lang, body):
    """Name the exception a comment falls under, or None when it is a violation."""
    text = body.strip().lstrip("*!/ ").strip()
    if GENERATED.search(text):
        return "generated"
    if lang == "ts" and ESLINT_NEXT_LINE.match(text):
        return "eslint-disable-next-line"
    for pat in cfg.allow_patterns:
        if pat.search(text):
            return pat.pattern
    return None


def without(src, spans):
    """Blank the given spans, keeping line numbers."""
    out, last = [], 0
    for start, end in spans:
        out.append(src[last:start])
        out.append("".join("\n" if c == "\n" else " " for c in src[start:end]))
        last = end
    out.append(src[last:])
    return "".join(out)


def test_names(text, lang):
    """Yield (where, pos, value) for each test title, skip reason and declared name in a test file."""
    if lang == "ts":
        for m in TS_TITLE.finditer(text):
            yield "title", m.start(), m.group(2)
    elif lang == "swift":
        for m in SWIFT_TITLE.finditer(text):
            yield "title", m.start(), m.group(1)
        for m in SWIFT_REASON.finditer(text):
            for s in SWIFT_STRING.finditer(m.group(1)):
                yield "reason", m.start(), s.group(1)
        for m in SWIFT_NAME.finditer(text):
            yield "name", m.start(), m.group(1)


def fingerprint(body):
    return hashlib.sha1(" ".join(body.split()).encode("utf-8")).hexdigest()[:8]


def measure(root, cfg):
    files = source_files(root, cfg)
    found = {r: [] for r in RULES}
    roots = defaultdict(lambda: {"files": 0, "lines": 0, "comment": 0, "history-id": 0})
    languages = defaultdict(lambda: {"files": 0, "lines": 0, "comment": 0})
    kinds, allows = Counter(), Counter()
    for f in files:
        lang = language_of(f)
        src = read(root, f)
        starts = [0] + [m.end() for m in re.finditer("\n", src)]

        def line_of(pos):
            return bisect.bisect_right(starts, pos)

        area, by_lang = roots[cfg.root_of(f)], languages[lang]
        for bucket in (area, by_lang):
            bucket["files"] += 1
            bucket["lines"] += len(src.splitlines())
        comments = LEXERS[lang](src)
        seen = Counter()
        for start, _, kind, body in comments:
            exception = allowed(cfg, lang, body)
            if exception:
                allows[exception] += 1
                continue
            target = f"{kind}:{fingerprint(body)}"
            seen[target] += 1
            text = " ".join(body.split())[:100]
            found["comment"].append(violation("comment", f, f"{target} #{seen[target]}", line_of(start), kind, text))
            area["comment"] += 1
            by_lang["comment"] += 1
            kinds[f"{lang}:{kind}"] += 1
        if not cfg.is_test(f):
            continue
        names = []
        stem = os.path.basename(f).split(".")[0]
        names.append(("file-name", 0, os.path.basename(f), cfg.history_text.search(stem) or cfg.history_ident.search(stem)))
        if lang != "css":
            text = without(src, [(s, e) for s, e, _, _ in comments])
            for where, pos, value in test_names(text, lang):
                pattern = cfg.history_ident if where == "name" else cfg.history_text
                names.append((where, line_of(pos), value, pattern.search(value)))
        for where, line, value, m in names:
            if not m:
                continue
            target = f"{where}:{' '.join(m.group(0).lower().split())}"
            seen[target] += 1
            found["history-id"].append(violation("history-id", f, f"{target} #{seen[target]}", line, where, value[:100]))
            area["history-id"] += 1
    for bucket in list(roots.values()) + list(languages.values()):
        bucket["comment per 1k"] = round(bucket["comment"] * 1000 / bucket["lines"], 2) if bucket["lines"] else 0.0
    return {
        "files": len(files),
        "roots": dict(sorted(roots.items())),
        "languages": dict(sorted(languages.items())),
        "kinds": dict(kinds.most_common()),
        "allowed": dict(allows.most_common()),
        "violations": {r: sorted(found[r], key=lambda v: (v["file"], v["line"])) for r in RULES},
    }


def violation(rule, file, target, line, kind, text):
    return {"rule": rule, "key": f"{rule}|{file}|{target}", "file": file, "line": line, "kind": kind, "text": text}


def check(report, cfg, baseline, base_baseline, base_config):
    problems = []
    known = set(baseline.get("known", []))
    current_keys = set()
    for rule in RULES:
        mode = cfg.rules[rule]
        for v in report["violations"][rule]:
            current_keys.add(v["key"])
            if mode == "off":
                continue
            if mode == "strict" or v["key"] not in known:
                problems.append(f"{v['file']}:{v['line']}: [{rule}] {v['kind']} \"{v['text'][:60]}\" — fix: {FIX[rule]}")
    for key in sorted(known):
        rule = key.split("|", 1)[0]
        if rule not in RULES:
            problems.append(f"baseline: [unknown-rule] {key}. Remove it")
        elif cfg.rules[rule] == "strict":
            problems.append(f"baseline: [stale] {key}: the rule is strict now. Remove it (run check.py --write-baseline)")
        elif key not in current_keys and cfg.rules[rule] == "baseline":
            problems.append(f"baseline: [stale] {key} no longer occurs. Remove it (run check.py --write-baseline)")
    warnings = []
    if base_baseline is not None:
        for key in sorted(known - set(base_baseline.get("known", []))):
            problems.append(f"baseline: [grew] {key} was added — fix the violation instead of recording it")
    if base_config is not None:
        order = {m: i for i, m in enumerate(MODES)}
        for rule in RULES:
            before = base_config.get("rules", {}).get(rule, "strict")
            if order.get(cfg.rules[rule], 0) < order.get(before, 0):
                warnings.append(f"config: rule {rule} loosened from {before} to {cfg.rules[rule]}")
        for p in sorted(set(cfg.exclude) - set(base_config.get("exclude", []))):
            warnings.append(f"config: exclude {p} added; files it matches are no longer checked")
        for p in sorted(set(cfg.allow) - set(base_config.get("allow", []))):
            warnings.append(f"config: allow {p} added; comments it matches no longer count")
        for p in sorted(set(base_config.get("tests", [])) - set(cfg.tests)):
            warnings.append(f"config: tests {p} removed; files it matched are no longer checked for history ids")
        for k in sorted(set(base_config.get("ticket_keys", [])) - set(cfg.ticket_keys)):
            warnings.append(f"config: ticket key {k} removed; its ids no longer count")
    return problems, warnings


def write_baseline(path, report, cfg):
    known = sorted(v["key"] for r in RULES if cfg.rules[r] == "baseline" for v in report["violations"][r])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"known": known}, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return known


def at_ref(root, ref, rel):
    text = git(root, "show", f"{ref}:{rel}")
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="repo root (default: git top level, else the current directory)")
    ap.add_argument("--config", help=f"config path (default: {DEFAULT_DIR}/config.json)")
    ap.add_argument("--baseline", help=f"baseline path (default: {DEFAULT_DIR}/baseline.json)")
    ap.add_argument("--base", help="git ref whose baseline may not be exceeded, e.g. origin/main")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write-baseline", action="store_true")
    mode.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)

    root = args.root or (git(".", "rev-parse", "--show-toplevel") or "").strip() or os.getcwd()
    config_path = args.config or os.path.join(root, DEFAULT_DIR, "config.json")
    baseline_path = args.baseline or os.path.join(root, DEFAULT_DIR, "baseline.json")
    if not os.path.isfile(config_path):
        print(f"no-comments: no config at {config_path}", file=sys.stderr)
        return 2
    cfg = Config(load_json(config_path))
    report = measure(root, cfg)

    if args.report:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.write_baseline:
        known = write_baseline(baseline_path, report, cfg)
        print(f"no-comments: wrote {os.path.relpath(baseline_path, root)} ({len(known)} known violations)")
        return 0

    baseline = load_json(baseline_path) if os.path.isfile(baseline_path) else {}
    base_baseline = base_config = None
    if args.base:
        base_baseline = at_ref(root, args.base, os.path.relpath(baseline_path, root))
        base_config = at_ref(root, args.base, os.path.relpath(config_path, root))
    problems, warnings = check(report, cfg, baseline, base_baseline, base_config)
    for w in warnings:
        print(f"warning: {w}")
    if problems:
        print(f"no-comments: {len(problems)} problem(s)")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"no-comments: ok ({len(baseline.get('known', []))} known violation(s) left)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
