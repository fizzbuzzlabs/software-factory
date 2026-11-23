#!/usr/bin/env python3
"""never-swallow-a-failure audit helpers. Never installed into a repo; check.py is.

  audit.py propose --root DIR --out config.json
      Draft a config: source roots, excludes (tests, scripts, generated code), and each rule strict
      at zero, baseline above it. Prints per root the lines, each rule's count and violations per
      10k lines, the files with the most violations, and lint configs that mention a related rule.

  audit.py sample --root DIR --config config.json [--log REGEX] [--every N]
      The judgment sample. Classifies every non-empty catch block and .catch handler as PROPAGATE
      (throws, rejects, returns a typed failure or HTTP error, sets an error state), LOG (calls a
      logger or reporter) or OTHER, and lists Swift try? used inside an expression. Prints every
      OTHER catch and every such try?, where a default returned with no log hides, and every Nth
      PROPAGATE and LOG catch.

  audit.py lint --root DIR --config config.json --lint FILE [--lint FILE]
      Counts per root the failures the lint rules hold instead of check.py, from
      `eslint --format json` and `swiftlint lint --reporter json` output: floating and misused
      promises, empty catch blocks, .catch() callbacks that do nothing, and try!. Baselined ESLint
      findings count; an eslint-disable directive doesn't. Prints every finding.

Stdlib only, Python 3.9+.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check

SKIP_DIRS = {"node_modules", "dist", "build", ".git", "vendor", "Pods", "DerivedData", "coverage", ".next",
             "out", "docs", "workflows", "scripts", "e2e", "fixtures", "__mocks__", ".claude", "Carthage",
             "evals", "benchmarks", "examples", "stories", "storybook", "mocks", "prototypes", "migrations",
             "drizzle", "Generated", "generated", "Preview Content"}
TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|spec|specs|[A-Za-z]*Tests|[A-Za-z]*UITests)(/|$)")
TEST_FILE = re.compile(r"\.(test|spec)\.\w+$")
EXCLUDE = ["*.test.*", "*.spec.*", "*/__tests__/*", "*/__mocks__/*", "*/test/*", "*/tests/*", "*Tests/*"]
LINT_CONFIGS = re.compile(r"(^|/)(eslint\.config\.\w+|\.eslintrc(\.\w+)?|\.swiftlint\.ya?ml|biome\.jsonc?)$")
LINT_RULES = re.compile(r"no-floating-promises|no-misused-promises|no-empty\b|allowEmptyCatch|ignoreVoid|"
                        r"force_try|only_rules|noFloatingPromises")
LOG = re.compile(r"\b(console\.\w+|\w*[lL]og\w*\s*\(|\w*[lL]ogger\.\w+|report\w*\(|capture\w*\(|AppLog\.|"
                 r"\.(error|warning|notice|fault|critical)\()")
PROPAGATE = re.compile(r"\bthrow\b|\breject\(|\(throwing:|return\s+(err|e|error)\b|ok:\s*false|\.failure\b|"
                       r"\bfail\w*\(|status\(\s*[45]\d\d|,\s*[45]\d\d\s*\)|\.failed\b|set\w*Error|"
                       r"\w*[eE]rror\w*\s*=[^=]|onError|\bfatalError\(")
SWIFT_EXPR_TRY = re.compile(r"(?<![\w.])try\?")
TASK_SLEEP = re.compile(r"\s*await\s+Task\s*\.\s*sleep\b")
TS_CATCH_CALL = re.compile(r"\.\s*catch\s*\(")
TS_EMPTY_HANDLER = re.compile(r"(?:async)?(?:\([^()]*\)|[\w$]+)=>(?:\{\}|undefined|null|void0)"
                              r"|(?:async)?function[\w$]*\([^()]*\)\{\}")
CATCH_BEFORE = re.compile(r"(?<![\w$.])catch\s*(?:\([^()]*\)\s*)?$")
CATCH_CALL_BEFORE = re.compile(r"\.\s*catch\s*\(\s*$")
LINT = {
    "@typescript-eslint/no-floating-promises": lambda text, i: "floating-promise",
    "@typescript-eslint/no-misused-promises": lambda text, i: "misused-promise",
    "no-empty": lambda text, i: "empty-catch" if CATCH_BEFORE.search(text, max(0, i - 200), i) else None,
    "no-restricted-syntax": lambda text, i: ".catch" if CATCH_CALL_BEFORE.search(text, max(0, i - 200), i) else None,
    "force_try": lambda text, i: "force-try",
}


def tracked(root):
    return [check.norm_path(f) for f in (check.git(root, "ls-files") or "").splitlines()]


def production(files):
    out = []
    for f in files:
        parts = f.split("/")
        if check.language_of(f) is None or len(parts) < 2 or any(p in SKIP_DIRS for p in parts[:-1]):
            continue
        if TEST_DIR.search(f) or TEST_FILE.search(f):
            continue
        out.append(f)
    return out


def lint_mentions(root, files):
    hits = []
    for f in files:
        if LINT_CONFIGS.search(f):
            for no, line in enumerate(check.read(root, f).splitlines(), 1):
                if LINT_RULES.search(line):
                    hits.append(f"{f}:{no}: {line.strip()[:100]}")
    return hits


def propose(args):
    root = os.path.abspath(args.root)
    files = tracked(root)
    prod = production(files)
    if not prod:
        raise SystemExit("propose: no TypeScript/JavaScript or Swift sources found under a folder")
    roots = sorted({f.split("/")[0] for f in prod})
    skipped = set()
    for f in files:
        parts = f.split("/")
        if parts[0] not in roots:
            continue
        for i, part in enumerate(parts[1:-1], 1):
            if part in SKIP_DIRS:
                skipped.add("/".join(parts[:i + 1]))
                break
    skipped = sorted(skipped)
    cfg = {"roots": roots, "exclude": EXCLUDE + [p + "/*" for p in skipped], "rules": {}}
    report = check.measure(root, check.Config(cfg))
    cfg["rules"] = {r: "baseline" if report["violations"][r] else "strict" for r in check.RULES}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")

    print(f"Draft config: {args.out}")
    print(f"Excluded beyond tests: {', '.join(skipped) or 'none'}")
    print(f"\n| Root | Files | Lines | {' | '.join(check.RULES)} | Per 10k |")
    print("|---" * (len(check.RULES) + 4) + "|")
    for name, a in report["roots"].items():
        print(f"| {name} | {a['files']} | {a['lines']} | {' | '.join(str(a[r]) for r in check.RULES)} | {a['per 10k']} |")
    per_file = Counter(v["file"] for r in check.RULES for v in report["violations"][r])
    print("\nMost violations:")
    for f, n in per_file.most_common(10):
        print(f"  {n:4d}  {f}")
    print("\nLint configs mentioning a related rule:")
    for hit in lint_mentions(root, files) or ["none"]:
        print(f"  {hit}")


def handlers(text, lang):
    """Yield (pos, kind, body) for every catch block and .catch handler in stripped source."""
    catch = check.TS_CATCH if lang == "ts" else check.SWIFT_CATCH
    for m in catch.finditer(text):
        yield m.start(), "catch", text[m.end():check.closing(text, m.end() - 1)]
    if lang == "ts":
        for m in TS_CATCH_CALL.finditer(text):
            body = text[m.end():check.closing(text, m.end() - 1)]
            if not TS_EMPTY_HANDLER.fullmatch(re.sub(r"\s+", "", body)):
                yield m.start(), ".catch", body


def classify(body):
    if PROPAGATE.search(body):
        return "PROPAGATE"
    return "LOG" if LOG.search(body) else "OTHER"


def sample(args):
    global LOG
    if args.log:
        LOG = re.compile(args.log)
    root = os.path.abspath(args.root)
    cfg = check.Config(check.load_json(args.config))
    report = check.measure(root, cfg)
    flagged = {(v["file"], v["line"]) for v in report["violations"]["empty-catch"]}
    classes, rows, expr_try = Counter(), {"PROPAGATE": [], "LOG": [], "OTHER": []}, []
    for f in check.source_files(root, cfg):
        lang = check.language_of(f)
        raw = check.read(root, f)
        text = check.strip_ts(raw) if lang == "ts" else check.strip_swift(raw)
        lines = raw.splitlines()
        for pos, kind, body in handlers(text, lang):
            line = text.count("\n", 0, pos) + 1
            if (f, line) in flagged or not body.strip():
                continue
            c = classify(body)
            classes[c] += 1
            first = " ".join(body.split())[:90]
            rows[c].append(f"{f}:{line}  {kind}  {first}")
        if lang == "swift":
            statements = {v["line"] for v in report["violations"]["discarded-try"] if v["file"] == f}
            seen = set()
            for m in SWIFT_EXPR_TRY.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                if line in statements or line in seen or TASK_SLEEP.match(text, m.end()):
                    continue
                seen.add(line)
                expr_try.append(f"{f}:{line}  {lines[line - 1].strip()[:110]}")
    print(f"Handlers (non-empty): {sum(classes.values())}, {json.dumps(dict(classes))}")
    print(f"\nOTHER, open every one ({len(rows['OTHER'])}):")
    for row in rows["OTHER"]:
        print(f"  {row}")
    print(f"\nSwift try? inside an expression, open every one ({len(expr_try)}):")
    for row in expr_try:
        print(f"  {row}")
    for c in ("PROPAGATE", "LOG"):
        print(f"\n{c}, every {args.every}th of {len(rows[c])}:")
        for row in rows[c][::args.every]:
            print(f"  {row}")


def lint_findings(root, files, paths, rows):
    """{"file", "line", "kind"} for each ESLint or SwiftLint JSON finding in files whose rule is in rows.
    rows maps a rule id to a function of (stripped source, offset) giving the kind, or None to drop it."""
    real, texts, out = os.path.realpath(root), {}, []
    for path in paths:
        for entry in check.load_json(path):
            if "filePath" in entry:
                name = entry["filePath"]
                kept = entry.get("messages", []) + [
                    m for m in entry.get("suppressedMessages", [])
                    if all(s.get("kind") != "directive" for s in m.get("suppressions", []))]
                found = [(m.get("ruleId"), m.get("line"), m.get("column")) for m in kept]
            else:
                name = entry.get("file") or ""
                found = [(entry.get("rule_id"), entry.get("line"), entry.get("character"))]
            rel = check.norm_path(os.path.relpath(os.path.realpath(os.path.join(root, name)), real))
            if rel not in files:
                continue
            for rule, line, col in found:
                if rule not in rows or not line:
                    continue
                if rel not in texts:
                    src = check.read(root, rel)
                    texts[rel] = check.strip_ts(src) if check.language_of(rel) == "ts" else check.strip_swift(src)
                text = texts[rel]
                start = sum(len(s) + 1 for s in text.split("\n")[:line - 1])
                kind = rows[rule](text, start + (col or 1) - 1)
                if kind:
                    out.append({"file": rel, "line": line, "kind": kind})
    return sorted(out, key=lambda v: (v["file"], v["line"]))


def lint(args):
    root = os.path.abspath(args.root)
    cfg = check.Config(check.load_json(args.config))
    report = check.measure(root, cfg)
    found = lint_findings(root, set(check.source_files(root, cfg)), args.lint, LINT)
    kinds = sorted({v["kind"] for v in found})
    per_root = {name: Counter() for name in report["roots"]}
    for v in found:
        per_root[cfg.root_of(v["file"])][v["kind"]] += 1
    print("| " + " | ".join(["Root", "Lines", *kinds, "check.py + lint per 10k"]) + " |")
    print("|---" * (len(kinds) + 3) + "|")
    for name, a in report["roots"].items():
        total = sum(a[r] for r in check.RULES) + sum(per_root[name].values())
        rate = round(total * 10000 / a["lines"], 2) if a["lines"] else 0.0
        print("| " + " | ".join([str(name), str(a["lines"]), *(str(per_root[name][k]) for k in kinds), str(rate)]) + " |")
    print(f"\nLint findings ({len(found)}):")
    for v in found:
        print(f"  {v['file']}:{v['line']}  {v['kind']}")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--root", default=".")
    s.add_argument("--config", required=True)
    s.add_argument("--log", help="regex for a call through the repo's logger or reporter, replacing the default")
    s.add_argument("--every", type=int, default=6)
    li = sub.add_parser("lint")
    li.add_argument("--root", default=".")
    li.add_argument("--config", required=True)
    li.add_argument("--lint", action="append", required=True,
                    help="eslint --format json or swiftlint lint --reporter json output; repeatable")
    args = ap.parse_args(argv)
    {"propose": propose, "sample": sample, "lint": lint}[args.cmd](args)


if __name__ == "__main__":
    main(sys.argv[1:])
