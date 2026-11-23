#!/usr/bin/env python3
"""no-comments audit helpers. Never installed into a repo; check.py is.

  audit.py propose --root DIR --out config.json
      Draft a config: source roots, excludes (generated and vendored code), test globs, ticket keys
      read from git history, no extra allowed patterns, and each rule strict at zero, baseline above
      it. Prints per root and language the lines, comments and rate per 1k, the most common leading
      words of the comments (lint directives show up here), and the most commented files.

  audit.py sample --root DIR --config config.json [--every N]
      The judgment sample. Prints every Nth comment, tagged `code` when it reads as commented-out
      code and `history` when it carries a history id, and every history-id violation.

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
             "out", "docs", "workflows", ".claude", "Carthage", "drizzle", "migrations", "Preview Content"}
GENERATED_DIRS = {"Generated", "generated", "__generated__"}
TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|spec|specs|[A-Za-z]*Tests|[A-Za-z]*UITests)(/|$)")
TEST_FILE = re.compile(r"\.(test|spec)\.\w+$")
TICKET = re.compile(r"\b([A-Z]{2,10})-\d+\b")
NOT_TICKETS = {"UTF", "ISO", "SHA", "RFC", "ES", "HTTP", "TLS", "SSL", "AES", "CVE", "GPT", "ECMA", "IEEE", "WCAG", "UTC", "GMT",
               "QA", "AMB", "GAP", "FGM"}
CODEISH = re.compile(
    r"^\s*(?:(?:const|let|var|import|export|return|await|if|for|func|guard|case|private|public|static|struct|class|enum|self\.)\b"
    r"|[\w.\]\)]+\s*\(.*\)\s*;?\s*$|[\w.]+\s*[-+*/]?=\s*[^=].*;?$|[{}]\s*$|.*;\s*$)"
)
LEAD = re.compile(r"[@#]?[\w.-]+(?::[\w:.-]+)?:?")


def tracked(root):
    return [check.norm_path(f) for f in (check.git(root, "ls-files") or "").splitlines()]


def generated(root, f):
    head = "\n".join(check.read(root, f).splitlines()[:5])
    return ".generated." in os.path.basename(f) or bool(check.GENERATED.search(head))


def ticket_keys(root):
    log = check.git(root, "log", "-n", "2000", "--format=%s%n%b%n%D") or ""
    counts = Counter(k for k in TICKET.findall(log) if k not in NOT_TICKETS)
    if not counts:
        return [], counts
    top = counts.most_common(1)[0][1]
    return sorted(k for k, n in counts.items() if n >= max(3, top // 10)), counts


def test_globs(files):
    globs = {"*.test.*", "*.spec.*"} if any(TEST_FILE.search(f) for f in files) else set()
    for f in files:
        m = TEST_DIR.search(f)
        if m:
            globs.add(f[:m.end(2)] + "/*")
    return sorted(g for g in globs if not any(o != g and o.endswith("/*") and g.startswith(o[:-1]) for o in globs))


def propose(args):
    root = os.path.abspath(args.root)
    sources, excluded = [], set()
    for f in tracked(root):
        parts = f.split("/")
        if check.language_of(f) is None or len(parts) < 2 or any(p in SKIP_DIRS for p in parts[:-1]):
            continue
        gen_dir = next((i for i, p in enumerate(parts[:-1]) if p in GENERATED_DIRS), None)
        if gen_dir is not None:
            excluded.add("/".join(parts[:gen_dir + 1]) + "/*")
        elif generated(root, f):
            excluded.add(f)
        else:
            sources.append(f)
    if not sources:
        raise SystemExit("propose: no TypeScript/JavaScript, Swift or CSS sources found under a folder")
    keys, key_counts = ticket_keys(root)
    cfg = {
        "roots": sorted({f.split("/")[0] for f in sources}),
        "exclude": sorted(excluded),
        "tests": test_globs(sources),
        "allow": [],
        "ticket_keys": keys,
        "rules": {},
    }
    report = check.measure(root, check.Config(cfg))
    cfg["rules"] = {r: "baseline" if report["violations"][r] else "strict" for r in check.RULES}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")

    print(f"Draft config: {args.out}")
    print(f"Excluded as generated: {', '.join(cfg['exclude']) or 'none'}")
    print(f"Test globs: {', '.join(cfg['tests']) or 'none'}")
    print(f"Ticket keys in git history: {json.dumps(dict(key_counts.most_common(8)))}; drafted {keys or 'none'}")
    print("\n| Root | Files | Lines | Comments | Per 1k | History ids |\n|---|---|---|---|---|---|")
    for name, a in report["roots"].items():
        print(f"| {name} | {a['files']} | {a['lines']} | {a['comment']} | {a['comment per 1k']} | {a['history-id']} |")
    print("\n| Language | Files | Lines | Comments | Per 1k |\n|---|---|---|---|---|")
    for name, a in report["languages"].items():
        print(f"| {name} | {a['files']} | {a['lines']} | {a['comment']} | {a['comment per 1k']} |")
    print(f"\nComment kinds: {json.dumps(report['kinds'])}")
    print(f"Allowed: {json.dumps(report['allowed'])}")
    leads = Counter()
    for v in report["violations"]["comment"]:
        m = LEAD.match(v["text"])
        if m:
            leads[m.group(0)] += 1
    print("Leading words (allow candidates when a lint directive):")
    for word, n in leads.most_common(12):
        print(f"  {n:4d}  {word}")
    print("Most commented files:")
    for f, n in Counter(v["file"] for v in report["violations"]["comment"]).most_common(10):
        print(f"  {n:4d}  {f}")


def sample(args):
    root = os.path.abspath(args.root)
    cfg = check.Config(check.load_json(args.config))
    report = check.measure(root, cfg)
    comments = report["violations"]["comment"]
    tags, rows = Counter(), []
    for v in comments:
        tag = []
        if v["kind"] in ("line", "block") and CODEISH.match(v["text"]):
            tag.append("code")
        if cfg.history_text.search(v["text"]):
            tag.append("history")
        tags.update(tag)
        rows.append(f"{v['file']}:{v['line']}  {v['kind']}{' [' + ','.join(tag) + ']' if tag else ''}  {v['text']}")
    print(f"Comments: {len(comments)}, commented-out code {tags['code']}, carrying a history id {tags['history']}")
    for row in rows[::args.every]:
        print(f"  {row}")
    ids = report["violations"]["history-id"]
    print(f"\nHistory ids in test names: {len(ids)}, by place {json.dumps(dict(Counter(v['kind'] for v in ids)))}")
    for v in ids:
        print(f"  {v['file']}:{v['line']}  {v['kind']}  {v['text']}")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--root", default=".")
    s.add_argument("--config", required=True)
    s.add_argument("--every", type=int, default=5)
    args = ap.parse_args(argv)
    {"propose": propose, "sample": sample}[args.cmd](args)


if __name__ == "__main__":
    main(sys.argv[1:])
