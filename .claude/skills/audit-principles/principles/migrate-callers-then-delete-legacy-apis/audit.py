#!/usr/bin/env python3
"""migrate-callers-then-delete-legacy-apis audit helpers. Never installed into a repo; check.py is.

  audit.py propose --root DIR --out config.json [--language ts|swift]
      Draft a config: source roots, caller-only roots (tests, evals), excludes, TypeScript path
      aliases. Then read history for every re-export with callers: a symbol once defined in the
      re-exporting file was moved, and stays a violation; one never defined there is proposed as a
      facade. Likewise an alias whose name was never defined before the commit that made it an alias
      was born one, and is proposed as a facade. Prints each candidate with its callers and the commit
      that decided it; writes the draft.

  audit.py history --root DIR [--commits N] [--grep REGEX]
      Mainline commits whose subject suggests a replacement API, for the same-wave sample.

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
             "out", "docs", "workflows", "scripts", "fixtures", "__mocks__", ".claude", "Carthage", "examples",
             "stories", "storybook", "mocks", "prototypes", "migrations", "drizzle", "Preview Content"}
TOP_SKIP = {"controls", "reports", "skills", "tools", "infra"}
TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|spec|specs|e2e|evals|benchmarks|[A-Za-z]*Tests|[A-Za-z]*UITests)(/|$)")
TEST_FILE = ("*.test.*", "*.spec.*")
REPLACEMENT = (r"(renam|replac|supersed|move .* to|extract|split|defined once|single definition|instead of|drop|"
               r"remove|retire|port of|generated|shared|deprecat|migrat|legacy)")


def git(root, *args):
    return check.git(root, *args) or ""


def tracked(root):
    return [check.norm_path(f) for f in git(root, "ls-files").splitlines()]


def detect_language(files):
    counts = Counter()
    for f in files:
        for lang, exts in check.EXTENSIONS.items():
            if f.endswith(exts) and not f.endswith(".d.ts"):
                counts[lang] += 1
    if not counts:
        raise SystemExit("propose: no TypeScript/JavaScript or Swift sources found")
    return counts.most_common(1)[0][0]


def layout(files, lang):
    exts = check.EXTENSIONS[lang]
    roots, caller_roots, nested_tests = set(), set(), set()
    for f in files:
        parts = f.split("/")
        if (len(parts) < 2 or not f.endswith(exts) or f.endswith(".d.ts") or parts[0] in TOP_SKIP
                or any(p in SKIP_DIRS for p in parts[:-1])):
            continue
        m = TEST_DIR.search(f)
        if m and m.start() == 0:
            caller_roots.add(parts[0])
        elif m:
            nested_tests.add(f[:m.end()].rstrip("/"))
            roots.add(parts[0])
        else:
            roots.add(parts[0])
    exclude = list(TEST_FILE) + sorted(t + "/*" for t in nested_tests)
    for r in sorted(roots):
        for f in files:
            parts = f.split("/")
            if parts[0] == r and any(p in SKIP_DIRS for p in parts[1:-1]):
                skip = next(p for p in parts[1:-1] if p in SKIP_DIRS)
                pattern = f[:f.index("/" + skip + "/") + len(skip) + 1] + "/*"
                if pattern not in exclude:
                    exclude.append(pattern)
    return sorted(roots), sorted(caller_roots), exclude


def strip_jsonc(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r'^\s*//.*$|(?<=[,{\[\s])//[^"\n]*$', "", text, flags=re.M)
    return re.sub(r",(\s*[}\]])", r"\1", text)


def ts_aliases(root, files):
    aliases = {}
    for f in files:
        if not re.search(r"(^|/)tsconfig[\w.-]*\.json$", f) or any(p in SKIP_DIRS for p in f.split("/")):
            continue
        try:
            opts = json.loads(strip_jsonc(check.read(root, f))).get("compilerOptions", {})
        except ValueError:
            continue
        base = os.path.normpath(os.path.join(os.path.dirname(f), opts.get("baseUrl", ".")))
        for pattern, targets in (opts.get("paths") or {}).items():
            if not pattern.endswith("*") or not targets or not targets[0].endswith("*"):
                continue
            target = check.norm_path(os.path.normpath(os.path.join(base, targets[0][:-1])))
            aliases.setdefault(pattern[:-1], target + "/")
    return aliases


def declaration(symbol):
    return (r"(interface|type|class|enum|function|const|let|var|namespace|struct|protocol|actor|typealias)[[:space:]]+"
            + re.escape(symbol) + r"([^A-Za-z0-9_$]|$)")


def defined_here(root, rel, symbol):
    """The latest commit whose diff adds or removes a definition of `symbol` in `rel`, or None."""
    out = git(root, "log", "--follow", "-n1", "-G", declaration(symbol), "--format=%h %ad %s", "--date=short", "--", rel)
    return out.strip() or None


def defined_before(root, symbol, sha):
    """The latest commit before `sha`, anywhere in the repo, that adds or removes a definition of `symbol`."""
    out = git(root, "log", "-n1", "-G", declaration(symbol), "--format=%h %ad %s", "--date=short", f"{sha}^")
    return out.strip() or None


def added_in(root, rel, line):
    out = git(root, "log", "--follow", "-S", line.strip(), "--format=%h %ad %s", "--date=short", "--", rel)
    return (out.splitlines() or [None])[-1]


def propose(args):
    root = os.path.abspath(args.root)
    files = tracked(root)
    lang = args.language or detect_language(files)
    roots, caller_roots, exclude = layout(files, lang)
    if not roots:
        raise SystemExit("propose: no production source folders found")
    cfg = {"language": lang, "roots": roots, "caller_roots": caller_roots, "exclude": exclude}
    if lang == "ts":
        cfg["aliases"] = ts_aliases(root, files)
        cfg["mount_methods"] = ["route"]
    cfg["facades"] = []
    cfg["rules"] = {r: "strict" for r in check.RULES}
    cfg["ratchets"] = {"callers": "on"}

    report = check.measure(root, check.Config(cfg))
    facades, rows = {}, []
    for rule in check.RULES:
        for v in report["violations"][rule]:
            text = check.read(root, v["file"])
            if rule == "reexport-shim" and v["symbol"] != "*":
                commit = defined_here(root, v["file"], v["symbol"])
                if commit is None:
                    facades.setdefault(v["file"], []).append(v["symbol"])
                    rows.append((rule, v, "facade: never defined here"))
                    continue
                rows.append((rule, v, f"moved: {commit}"))
            elif rule == "alias-rename":
                line = next((l for l in text.splitlines() if re.search(r"\b" + re.escape(v["symbol"]) + r"\b", l)), "")
                added = added_in(root, v["file"], line)
                prior = added and defined_before(root, v["symbol"], added.split()[0])
                if added and not prior:
                    facades.setdefault(v["file"], []).append(v["symbol"])
                    rows.append((rule, v, f"facade: born an alias in {added}"))
                    continue
                rows.append((rule, v, f"renamed: defined in {prior or 'unknown'}, aliased in {added or 'unknown'}"))
            else:
                rows.append((rule, v, ""))
    cfg["facades"] = [{"path": f, "symbols": sorted(s)} for f, s in sorted(facades.items())]
    report = check.measure(root, check.Config(cfg))
    cfg["rules"] = {r: "baseline" if report["violations"][r] else "strict" for r in check.RULES}

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")

    print(f"language: {lang}   roots: {', '.join(roots)}   caller roots: {', '.join(caller_roots) or 'none'}")
    print(f"exclude: {', '.join(exclude)}")
    if cfg.get("aliases"):
        print(f"aliases: {json.dumps(cfg['aliases'])}")
    print(f"production files: {report['files']} ({report['production_lines']} lines)   caller-only files: {report['caller_files']}")
    print(f"\nsites: {len(report['sites'])} = {report['sites_per_10k_lines']} per 10k production lines")
    print(f"violations under this draft: {json.dumps({r: len(v) for r, v in report['violations'].items()})}")
    print(f"unused compatibility layers (dead code, not counted): {len(report['unused'])}")
    print("\ncandidates (rule, site, symbol, callers, history):")
    for rule, v, verdict in rows:
        n = len(v["callers"]) if v["callers"] is not None else "-"
        print(f"  {rule:13s} {v['file']}  {v['symbol']}  callers {n}  {verdict}")
    if cfg["facades"]:
        print(f"\nproposed facades: {', '.join(f['path'] for f in cfg['facades'])}")
    print(f"\ndraft written to {args.out}")
    return 0


def history(args):
    root = os.path.abspath(args.root)
    pattern = args.grep or REPLACEMENT
    total = git(root, "rev-list", "--first-parent", "--count", "HEAD").strip()
    log = git(root, "log", "--first-parent", f"-n{args.commits}", "--format=%h %ad%x1f%s%x1f%b%x1e", "--date=short")
    rows = []
    for entry in log.split("\x1e"):
        if not entry.strip():
            continue
        head, subject, body = (entry.strip("\n").split("\x1f") + ["", ""])[:3]
        if subject.startswith("Merge pull request") and body.strip():
            subject = body.strip().splitlines()[0]
        if re.search(pattern, subject, re.I) and not re.search(r"(?i)review pool|merge train|^(docs|ci|chore)\b", subject):
            rows.append(f"{head} {subject}")
    print(f"{len(rows)} candidate replacement commit(s) of {total} mainline commits (open 10–12 for the same-wave sample):")
    for l in rows:
        print(f"  {l}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True)
    p.add_argument("--language", choices=sorted(check.EXTENSIONS))
    h = sub.add_parser("history")
    h.add_argument("--root", default=".")
    h.add_argument("--commits", type=int, default=400)
    h.add_argument("--grep", help="regex for replacement commit subjects (default covers renames, moves, removals)")
    args = ap.parse_args(argv)
    return propose(args) if args.cmd == "propose" else history(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
