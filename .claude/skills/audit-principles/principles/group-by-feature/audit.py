#!/usr/bin/env python3
"""group-by-feature audit helpers. Never installed into a repo; check.py is.

  audit.py propose --root DIR --out config.json [--language ts|swift] [--commits N]
      Draft a feature map for a repo: source roots, feature / kernel / shell folders, kind
      folders whose files belong to features, large files spanning several features, and the
      edges observed between features (proposed as may_use, per path when a feature's paths
      use different features). Prints a summary; writes the draft.

  audit.py scatter --root DIR --config config.json [--commits N] [--ticket REGEX] [--ignore REGEX]
      History scatter under a feature map: distinct features touched per ticket (or per commit
      when no ticket pattern is given). Prints median, p90 and the highest-scatter units of work.

Stdlib only, Python 3.9+.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check

SKIP_DIRS = {"node_modules", "dist", "build", ".git", "vendor", "Pods", "DerivedData", "coverage", ".next",
             "out", "docs", "workflows", "scripts", "e2e", "fixtures", "__mocks__", ".claude", "Carthage",
             "evals", "benchmarks", "examples", "stories", "storybook", "mocks", "prototypes", "migrations",
             "drizzle", "Preview Content"}
TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|spec|specs|[A-Za-z]*Tests|[A-Za-z]*UITests)(/|$)")
SHARED_NAMES = {"utils", "util", "helpers", "helper", "lib", "libs", "common", "shared", "core", "kernel",
                "platform", "types", "constants", "config", "logging", "networking", "extensions", "brand",
                "theme", "ui", "design", "designsystem", "generated", "assets", "resources", "styles",
                "middleware", "infra", "foundation", "shell", "layout"}
LAYER_NAMES = {"components", "component", "services", "service", "models", "model", "views", "view",
               "controllers", "controller", "stores", "store", "hooks", "api", "apis", "routes", "router",
               "routers", "screens", "pages", "reducers", "actions", "selectors", "slices", "entities",
               "repositories", "repository", "dto", "dtos", "schemas", "providers", "contexts", "context",
               "widgets", "presentation", "data", "domain", "adapters", "handlers", "clients", "viewmodels",
               "transport", "state", "containers", "managers", "coordinators", "usecases"}
CONTAINER_NAMES = {"features", "feature", "modules", "module", "domains", "apps", "packages"}
SHELL_DIRS = {"app", "App", "application", "Application"}
STYLE_EXTS = (".css", ".scss", ".sass", ".less", ".styl")
RESERVED = {"kernel", "shell"}
SHELL_FILES = re.compile(r"^(main|index|app|server|App|AppDelegate|SceneDelegate|[A-Z]\w*App|[\w-]*(builder|registry|bootstrap))\.\w+$")


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


def production(files, lang):
    exts = check.EXTENSIONS[lang]
    out = []
    for f in files:
        parts = f.split("/")
        if not f.endswith(exts) or f.endswith(".d.ts") or any(p in SKIP_DIRS for p in parts[:-1]):
            continue
        if TEST_DIR.search(f) or re.search(r"\.(test|spec)\.\w+$", f):
            continue
        out.append(f)
    return out


def find_roots(files):
    tops = Counter(f.split("/")[0] for f in files if "/" in f)
    roots = []
    for top in tops:
        under = [f for f in files if f.startswith(top + "/")]
        src = [f for f in under if f.startswith(top + "/src/")]
        if top == "Sources":
            roots += sorted({"/".join(f.split("/")[:2]) for f in under if f.count("/") >= 2})
        elif len(src) >= 0.6 * len(under):
            roots.append(top + "/src")
            roots += sorted({"/".join(f.split("/")[:2]) for f in under
                             if f.count("/") >= 2 and not f.startswith(top + "/src/")})
        else:
            roots.append(top)
    return sorted(set(roots))


def tokens(name):
    stem = re.sub(r"\.\w+$", "", os.path.basename(name))
    parts = re.split(r"[-_.\s]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", stem)
    return [p.lower() for p in parts if p]


def singular(word):
    for suffix, repl in (("ies", "y"), ("sses", "ss"), ("s", "")):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)] + repl
    return word


def classify(roots, files):
    features, kernel, shell, layers = {}, [], [], []
    loose = []
    for root in roots:
        if os.path.basename(root) in SHELL_DIRS:
            shell.append(root)
            continue
        if os.path.basename(root).lower() in SHARED_NAMES:
            kernel.append(root)
            continue
        children = defaultdict(list)
        for f in files:
            if not f.startswith(root + "/"):
                continue
            rest = f[len(root) + 1:]
            if "/" in rest:
                children[rest.split("/")[0]].append(f)
            elif SHELL_FILES.match(rest):
                shell.append(f)
            else:
                loose.append(f)
        for child, members in sorted(children.items()):
            path = f"{root}/{child}"
            low = child.lower()
            if low in CONTAINER_NAMES:
                for f in members:
                    rest = f[len(path) + 1:]
                    if "/" in rest:
                        name = rest.split("/")[0]
                        key = name if name not in RESERVED else f"{name}-feature"
                        features.setdefault(key, set()).add(f"{path}/{name}")
                    else:
                        loose.append(f)
            elif child in SHELL_DIRS:
                shell.append(path)
            elif low in SHARED_NAMES or low in RESERVED:
                kernel.append(path)
            elif low in LAYER_NAMES:
                layers.append(path)
            else:
                features.setdefault(child, set()).add(path)
    return features, sorted(set(kernel)), sorted(set(shell)), sorted(set(layers)), sorted(loose)


def match_feature(f, feature_tokens):
    toks = {singular(t) for t in tokens(f)}
    hits = [name for name, ftoks in feature_tokens.items() if ftoks and ftoks <= toks]
    return max(hits, key=lambda n: len(feature_tokens[n])) if hits else None


def propose(args):
    root = os.path.abspath(args.root)
    files_all = tracked(root)
    lang = args.language or detect_language(files_all)
    files = production(files_all, lang)
    roots = find_roots(files)
    features, kernel, shell, layers, loose = classify(roots, files)
    feature_tokens = {name: {singular(t) for t in tokens(name)} for name in features}

    recurring = defaultdict(set)
    for layer in layers:
        for f in files:
            if f.startswith(layer + "/") and not match_feature(f, feature_tokens):
                for t in {singular(t) for t in tokens(f)}:
                    if len(t) > 2 and t not in LAYER_NAMES and t not in SHARED_NAMES and t not in {"use", "index"}:
                        recurring[t].add(layer)
    planned = sorted(t for t, where in recurring.items() if len(where) >= 2)
    for t in planned:
        feature_tokens[t] = {t}

    moves, unmatched = defaultdict(list), []
    for layer in list(layers):
        members = [f for f in files if f.startswith(layer + "/")]
        matched = {f: match_feature(f, feature_tokens) for f in members}
        if sum(1 for n in matched.values() if n) * 2 < len(members):
            layers.remove(layer)
            kernel.append(layer)
            shared_moves = [(f, n) for f, n in matched.items() if n]
            for f, n in shared_moves:
                moves[n].append(f)
            continue
        for f, name in matched.items():
            (moves[name].append(f) if name else unmatched.append(f))
    kernel = sorted(set(kernel))
    new_features = planned

    cfg = {
        "language": lang,
        "roots": roots,
        "exclude": [],
        "features": {name: {"paths": sorted(paths)} for name, paths in sorted(features.items())},
        "planned_features": planned,
        "kernel": {"paths": kernel},
        "shell": {"paths": sorted(shell)},
        "rules": {r: "baseline" for r in check.RULES},
        "ratchets": {"shared-single-user": "on", "kind-files": [], "cross-feature-duplication": "on"},
    }
    if lang == "ts":
        for name, feature in cfg["features"].items():
            if all(any(f == f"{p}/{idx}" for f in files) for p in feature["paths"] for idx in ["index.ts"]):
                feature["public"] = ["index.ts"]

    observed = check.measure(root, check.FeatureMap(cfg))
    edges, path_edges = observed["feature_edges"], observed["path_edges"]
    mutual = sorted({tuple(sorted((a, b))) for a, bs in edges.items() for b in bs if a in edges.get(b, [])})
    split = {}
    for name, feature in cfg["features"].items():
        per_path = {p: path_edges.get(p, []) for p in feature["paths"]}
        if len({tuple(v) for v in per_path.values()}) > 1:
            split[name] = per_path
            feature["paths"] = [{"path": p, "may_use": v} for p, v in per_path.items()]
        elif edges.get(name):
            feature["may_use"] = edges[name]

    names = set(features) | set(new_features)
    kind_files = []
    outside = check.FeatureMap(cfg)
    for f in files_all:
        if any(p in SKIP_DIRS for p in f.split("/")[:-1]) or TEST_DIR.search(f) or "generated" in f.lower():
            continue
        if not f.endswith(check.EXTENSIONS[lang] + STYLE_EXTS):
            continue
        unit = outside.unit_of(f)
        if unit and unit[0] == "feature":
            continue
        text = check.read(root, f)
        n = text.count("\n")
        if n < 800:
            continue
        low = text.lower()
        mentioned = sorted(name for name in names if re.search(r"\b" + re.escape(singular(name.lower())), low))
        if len(mentioned) >= 3:
            kind_files.append((f, n, mentioned))
    cfg["ratchets"]["kind-files"] = [f for f, _, _ in kind_files]
    fmap = check.FeatureMap(cfg)
    report = check.measure(root, fmap)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")

    units = report["units"]
    print(f"language: {lang}   roots: {', '.join(roots)}   production files: {report['files']}")
    print("\nunits (files / lines):")
    for name, u in units.items():
        print(f"  {u['kind']:9s} {name:32s} {u['files']:5d} {u['lines']:7d}")
    print(f"\nkind folders holding feature code ({len(layers)}): {', '.join(layers) or 'none'}")
    print("files named after a feature but sitting outside it (proposed moves):")
    for name, fs in sorted(moves.items()):
        print(f"  -> {name}: {len(fs)} file(s), e.g. {', '.join(fs[:3])}")
    if unmatched:
        print(f"  unmatched: {len(unmatched)} file(s), e.g. {', '.join(unmatched[:5])}")
    if new_features:
        print(f"\nnames recurring across kind folders (proposed new features, no folder yet): {', '.join(new_features)}")
    if loose:
        print(f"\nloose files at a root ({len(loose)}): {', '.join(loose[:8])}")
    if kind_files:
        print("\nlarge files spanning several features (proposed kind-files ratchets):")
        for f, n, mentioned in kind_files:
            print(f"  {f} ({n} lines): {', '.join(mentioned[:8])}")
    print("\nobserved feature edges (proposed as may_use):")
    for a, bs in edges.items():
        print(f"  {a} -> {', '.join(bs)}")
        for p, ps in split.get(a, {}).items():
            print(f"    {p} -> {', '.join(ps) or '(none)'}")
    if mutual:
        print(f"mutual edges (two-cycle violations): {', '.join(a + ' <-> ' + b for a, b in mutual)}")
    counts = {r: len(v) for r, v in report["violations"].items()}
    print(f"\nviolations under this draft: {json.dumps(counts)}")
    print(f"ratchets: {json.dumps(check.ratchet_values(report['ratchets']))}")
    print(f"\ndraft written to {args.out}")
    if args.commits:
        print()
        scatter_report(root, fmap, args.commits, None, None)
    return 0


def scatter_report(root, fmap, commits, ticket, ignore):
    log = git(root, "log", "--no-merges", f"-n{commits}", "--name-only", "--format=@@%H%x09%s")
    units_of_work = defaultdict(lambda: {"features": set(), "kernel": False, "shell": False, "subject": ""})
    order = []
    sha = subject = None
    ignore_re = re.compile(ignore or r"(?i)\b(revert|format|prettier|rename|bump|lint|sweep|codegen|merge)\b")
    ticket_re = re.compile(ticket) if ticket else None
    skip = False
    for line in log.splitlines():
        if line.startswith("@@"):
            sha, subject = line[2:].split("\t", 1)
            skip = bool(ignore_re.search(subject))
            key = sha
            if ticket_re:
                m = ticket_re.search(subject)
                key = m.group(0) if m else None
            if key and not skip:
                if key not in units_of_work:
                    order.append(key)
                units_of_work[key]["subject"] = units_of_work[key]["subject"] or subject
            current = key if not skip else None
            continue
        if not line.strip() or current is None:
            continue
        u = fmap.unit_of(check.norm_path(line))
        if not u:
            continue
        kind, name = u
        if kind == "feature":
            units_of_work[current]["features"].add(name)
        else:
            units_of_work[current][kind] = True
    rows = [(k, units_of_work[k]) for k in order if units_of_work[k]["features"]]
    if not rows:
        print("scatter: no commits touch a mapped feature")
        return
    homes = [len(r["features"]) for _, r in rows]
    homes_sorted = sorted(homes)
    p90 = homes_sorted[min(len(homes_sorted) - 1, int(round(0.9 * (len(homes_sorted) - 1))))]
    hub = sum(1 for _, r in rows if r["kernel"] or r["shell"])
    print(f"scatter over {len(rows)} unit(s) of work ({'per ticket' if ticket_re else 'per commit'}): "
          f"features touched median {statistics.median(homes):g}, p90 {p90}, "
          f"touching 3+ features {sum(1 for h in homes if h >= 3)}, touching kernel or shell {hub}")
    print("highest scatter (open these for the judgment sample):")
    for key, r in sorted(rows, key=lambda kr: -len(kr[1]["features"]))[:10]:
        print(f"  {len(r['features']):2d}  {key[:12]:12s} {r['subject'][:70]}  [{', '.join(sorted(r['features']))}]")


def scatter(args):
    root = os.path.abspath(args.root)
    fmap = check.FeatureMap(check.load_json(args.config))
    scatter_report(root, fmap, args.commits, args.ticket, args.ignore)
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True)
    p.add_argument("--language", choices=sorted(check.EXTENSIONS))
    p.add_argument("--commits", type=int, default=200)
    s = sub.add_parser("scatter")
    s.add_argument("--root", default=".")
    s.add_argument("--config", required=True)
    s.add_argument("--commits", type=int, default=300)
    s.add_argument("--ticket", help="regex for a ticket id in commit subjects, e.g. '[A-Z]+-\\d+'")
    s.add_argument("--ignore", help="regex for commit subjects to skip (default: reverts, sweeps, renames, bumps)")
    args = ap.parse_args(argv)
    return propose(args) if args.cmd == "propose" else scatter(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
