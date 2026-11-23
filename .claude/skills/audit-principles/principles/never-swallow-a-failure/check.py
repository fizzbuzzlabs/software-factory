#!/usr/bin/env python3
"""never-swallow-a-failure check: production code never drops a failure without handling it.

Reads <dir>/config.json (source roots, excludes, how strict each rule is) and
<dir>/baseline.json (known violations), where <dir> defaults to controls/never-swallow-a-failure.
Exit 0 when clean, 1 on any failure, 2 on a usage error.

  check.py                     fail on new violations and stale baseline entries
  check.py --base origin/main  also fail when the baseline grew compared with that ref
  check.py --write-baseline    record today's violations
  check.py --report            print every measurement as JSON (rules in any mode)

Stdlib only, Python 3.9+. Languages: ts (TypeScript and JavaScript) and swift.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

DEFAULT_DIR = "controls/never-swallow-a-failure"
EXTENSIONS = {
    "ts": (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"),
    "swift": (".swift",),
}
RULES = ("empty-catch", "discarded-try", "throwing-task")
MODES = ("off", "baseline", "strict")
FIX = {
    "empty-catch": "handle the error, rethrow it, or log it with the operation and ids it failed on",
    "discarded-try": "use do/catch and log or surface the error; only try? await Task.sleep may drop it",
    "throwing-task": "catch inside the Task body and log or surface the error, or keep the Task and await its value",
}
TS_CATCH = re.compile(r"(?<![\w$.])catch\s*(?:\([^()]*\)\s*)?\{")
SWIFT_CATCH = re.compile(r"(?<![\w.])catch\b[^{}\n]*\{")
SWIFT_DISCARD = re.compile(r"(?m)^[ \t]*(?:_[ \t]*=[ \t]*)?try\?(?![ \t]*await[ \t]+Task[ \t]*\.[ \t]*sleep\b)")
SWIFT_TASK = re.compile(r"(?m)^[ \t]*(?:_[ \t]*=[ \t]*)?Task(?:[ \t]*\.[ \t]*detached)?[ \t]*(?:\([^()\n]*\))?[ \t]*\{")
SWIFT_TRY = re.compile(r"(?<![\w.])try(?![?!\w])")
SWIFT_CATCH_WORD = re.compile(r"(?<![\w.])catch\b")
SWIFT_CALLEE = re.compile(r"\s*(?:await\s+)?([\w.]+)")


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
        if rel.endswith(exts) and not rel.endswith(".d.ts"):
            return lang
    return None


class Config:
    def __init__(self, cfg):
        self.roots = [norm_path(r) for r in cfg.get("roots", [])]
        if not self.roots:
            raise SystemExit("config: roots must list at least one source directory")
        self.exclude = cfg.get("exclude", [])
        self.rules = {r: cfg.get("rules", {}).get(r, "strict") for r in RULES}
        for r, m in self.rules.items():
            if m not in MODES:
                raise SystemExit(f"config: rules.{r} must be one of {', '.join(MODES)}")

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


def blank(text):
    return "".join("\n" if c == "\n" else " " for c in text)


def strip_ts(src):
    """Blank comments and string text, keeping line numbers and template ${...} code."""
    out = []
    i, n = 0, len(src)
    while i < n:
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(blank(src[i:j]))
            i = j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(blank(src[i:j]))
            i = j
        elif src[i] in "'\"":
            j = i + 1
            while j < n and src[j] != src[i] and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(blank(src[i:j]))
            i = j
        elif src[i] == "`":
            out.append(" ")
            i += 1
            while i < n and src[i] != "`":
                if src[i] == "\\":
                    out.append(blank(src[i:i + 2]))
                    i += 2
                elif src[i:i + 2] == "${":
                    depth, j = 1, i + 2
                    while j < n and depth:
                        depth += {"{": 1, "}": -1}.get(src[j], 0)
                        j += 1
                    out.append("  " + strip_ts(src[i + 2:j - 1]) + " ")
                    i = j
                else:
                    out.append(blank(src[i]))
                    i += 1
            out.append(" ")
            i += 1
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def strip_swift(src):
    """Blank comments and string literals (raw and multi-line included), keeping line numbers."""
    out = []
    i, n = 0, len(src)
    while i < n:
        two = src[i:i + 2]
        if two == "//":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if two == "/*":
            depth = 1
            out.append("  ")
            i += 2
            while i < n and depth:
                if src[i:i + 2] == "/*":
                    depth += 1
                    out.append("  ")
                    i += 2
                elif src[i:i + 2] == "*/":
                    depth -= 1
                    out.append("  ")
                    i += 2
                else:
                    out.append("\n" if src[i] == "\n" else " ")
                    i += 1
            continue
        if src[i] == "#" or src[i] == '"':
            j = i
            while j < n and src[j] == "#":
                j += 1
            hashes = j - i
            if j < n and src[j] == '"':
                multi = src[j:j + 3] == '"""'
                quote = '"""' if multi else '"'
                close = quote + "#" * hashes
                k = j + len(quote)
                while k < n:
                    if hashes == 0 and src[k] == "\\":
                        k += 2
                        continue
                    if src.startswith(close, k):
                        k += len(close)
                        break
                    if not multi and src[k] == "\n":
                        break
                    k += 1
                out.append(blank(src[i:k]))
                i = k
                continue
        out.append(src[i])
        i += 1
    return "".join(out)


def closing(text, open_idx):
    """Index of the bracket that closes the one at open_idx, or len(text)."""
    depth = 0
    for k in range(open_idx, len(text)):
        if text[k] in "([{":
            depth += 1
        elif text[k] in ")]}":
            depth -= 1
            if depth == 0:
                return k
    return len(text)


def scan(src, text, lang):
    """Yield (rule, line, kind) for each violation. text is src with comments and strings blanked.
    TS: ESLint's no-empty finds an empty catch, so only one holding nothing but comments counts."""
    starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_of(pos):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    if lang == "ts":
        for m in TS_CATCH.finditer(text):
            end = closing(text, m.end() - 1)
            if not text[m.end():end].strip() and src[m.end():end].strip():
                yield "empty-catch", line_of(m.start()), "catch"
        return
    for m in SWIFT_CATCH.finditer(text):
        if not text[m.end():closing(text, m.end() - 1)].strip():
            yield "empty-catch", line_of(m.start()), "catch"
    for m in SWIFT_DISCARD.finditer(text):
        callee = SWIFT_CALLEE.match(text, m.end())
        yield "discarded-try", line_of(m.end()), f"try? {callee.group(1) if callee else ''}".strip()
    for m in SWIFT_TASK.finditer(text):
        body = text[m.end():closing(text, m.end() - 1)]
        if SWIFT_TRY.search(body) and not SWIFT_CATCH_WORD.search(body):
            yield "throwing-task", line_of(m.end()), "Task"


def violation(rule, file, kind, n, line):
    target = f"{kind} #{n}"
    return {"rule": rule, "key": f"{rule}|{file}|{target}", "file": file, "line": line, "kind": kind}


def measure(root, cfg):
    files = source_files(root, cfg)
    found = {r: [] for r in RULES}
    roots = defaultdict(lambda: dict({"files": 0, "lines": 0}, **{r: 0 for r in RULES}))
    for f in files:
        lang = language_of(f)
        src = read(root, f)
        area = roots[cfg.root_of(f)]
        area["files"] += 1
        area["lines"] += len(src.splitlines())
        text = strip_ts(src) if lang == "ts" else strip_swift(src)
        seen = Counter()
        for rule, line, kind in sorted(scan(src, text, lang), key=lambda s: s[1]):
            seen[(rule, kind)] += 1
            found[rule].append(violation(rule, f, kind, seen[(rule, kind)], line))
            area[rule] += 1
    for area in roots.values():
        total = sum(area[r] for r in RULES)
        area["per 10k"] = round(total * 10000 / area["lines"], 2) if area["lines"] else 0.0
    return {
        "files": len(files),
        "roots": dict(sorted(roots.items())),
        "violations": {r: sorted(found[r], key=lambda v: (v["file"], v["line"])) for r in RULES},
    }


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
                problems.append(f"{v['file']}:{v['line']}: [{rule}] {v['kind']} — fix: {FIX[rule]}")
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
        print(f"never-swallow-a-failure: no config at {config_path}", file=sys.stderr)
        return 2
    cfg = Config(load_json(config_path))
    report = measure(root, cfg)

    if args.report:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.write_baseline:
        known = write_baseline(baseline_path, report, cfg)
        print(f"never-swallow-a-failure: wrote {os.path.relpath(baseline_path, root)} ({len(known)} known violations)")
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
        print(f"never-swallow-a-failure: {len(problems)} problem(s)")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"never-swallow-a-failure: ok ({len(baseline.get('known', []))} known violation(s) left)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
