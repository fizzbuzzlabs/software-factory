#!/usr/bin/env python3
"""group-by-feature check: feature placement, boundaries and ratchets, from one config.

Reads <dir>/config.json (the feature map and how strict each rule is) and
<dir>/baseline.json (known violations and ratchet numbers), where <dir> defaults to
controls/group-by-feature. Exit 0 when clean, 1 on any failure, 2 on a usage error.

  check.py                     fail on new violations, stale baseline entries and ratchet changes
  check.py --base origin/main  also fail when the baseline grew compared with that ref
  check.py --write-baseline    record today's violations and ratchet numbers
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
from collections import defaultdict

DEFAULT_DIR = "controls/group-by-feature"
EXTENSIONS = {
    "ts": (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"),
    "swift": (".swift",),
}
RULES = ("placement", "kernel-uses-feature", "unlisted-edge", "deep-import", "two-cycle", "uses-shell")
MODES = ("off", "baseline", "strict")
RATCHETS = ("shared-single-user", "kind-files", "cross-feature-duplication")
FIX = {
    "placement": "move the file into a feature folder, the kernel or the shell. A new feature is a config change in a reviewed PR",
    "kernel-uses-feature": "the kernel must not depend on a feature. Move the code into the feature, or have the shell pass it in",
    "unlisted-edge": "this feature may not use that one. Move the code, depend on the kernel instead, or add the edge to may_use in a reviewed PR",
    "deep-import": "import the other feature through its public files only",
    "two-cycle": "these features depend on each other. Move the shared part to the kernel, or merge the features",
    "uses-shell": "only the shell may depend on the shell. Move the code out of the shell",
}
RATCHET_FIX = {
    "shared-single-user": "move kernel code that only one feature uses into that feature",
    "kind-files": "move each feature's part of this file into the feature's own folder",
    "cross-feature-duplication": "one feature owns the logic and the other calls it through its public files",
}


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


def path_entry(entry, where):
    """A paths entry is a string, or {"path": ..., "may_use": [...]} giving that path its own may_use."""
    if isinstance(entry, str):
        return norm_path(entry), None
    if isinstance(entry, dict) and isinstance(entry.get("path"), str):
        may_use = entry.get("may_use")
        if may_use is not None and not (isinstance(may_use, list) and all(isinstance(m, str) for m in may_use)):
            raise SystemExit(f"config: {where} may_use must be a list of feature names")
        return norm_path(entry["path"]), may_use
    raise SystemExit(f'config: {where} paths entries must be a string or {{"path": ..., "may_use": [...]}}')


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


class FeatureMap:
    def __init__(self, cfg):
        self.cfg = cfg
        self.language = cfg.get("language")
        if self.language not in EXTENSIONS:
            raise SystemExit(f"config: language must be one of {', '.join(EXTENSIONS)}")
        self.roots = [norm_path(r) for r in cfg.get("roots", [])]
        if not self.roots:
            raise SystemExit("config: roots must list at least one source directory")
        self.exclude = cfg.get("exclude", [])
        self.features = cfg.get("features", {})
        self.units = []
        self.feature_paths = {}
        self.path_may_use = {}
        for name, feature in self.features.items():
            self.feature_paths[name] = []
            for entry in feature.get("paths", []):
                p, may_use = path_entry(entry, f"features.{name}")
                self.feature_paths[name].append(p)
                if may_use is not None:
                    self.path_may_use[p] = may_use
                self.units.append((p, "feature", name))
        for p in cfg.get("kernel", {}).get("paths", []):
            self.units.append((norm_path(p), "kernel", "kernel"))
        for p in cfg.get("shell", {}).get("paths", []):
            self.units.append((norm_path(p), "shell", "shell"))
        self.units.sort(key=lambda u: len(u[0]), reverse=True)
        self.rules = {r: cfg.get("rules", {}).get(r, "strict") for r in RULES}
        for r, m in self.rules.items():
            if m not in MODES:
                raise SystemExit(f"config: rules.{r} must be one of {', '.join(MODES)}")
        self.ratchets = cfg.get("ratchets", {})
        self.aliases = {k: norm_path(v) + "/" for k, v in cfg.get("aliases", {}).items()}

    def unit_path(self, rel):
        for prefix, kind, name in self.units:
            if rel == prefix or rel.startswith(prefix + "/"):
                return prefix, kind, name
        return None

    def unit_of(self, rel):
        u = self.unit_path(rel)
        return u[1:] if u else None

    def may_use(self, src_file, dst):
        prefix, _, name = self.unit_path(src_file)
        allowed = self.path_may_use.get(prefix)
        if allowed is None:
            allowed = self.features.get(name, {}).get("may_use", [])
        return "*" in allowed or dst in allowed

    def is_public(self, rel, feature):
        public = self.features.get(feature, {}).get("public")
        if not public:
            return True
        for p in self.feature_paths[feature]:
            for entry in public:
                if rel == p + "/" + norm_path(entry):
                    return True
        return False


def source_files(root, fmap):
    exts = EXTENSIONS[fmap.language]
    listed = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--", *fmap.roots)
    if listed is None:
        listed_files = []
        for r in fmap.roots:
            for dirpath, dirnames, filenames in os.walk(os.path.join(root, r)):
                dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git", "dist", "build")]
                for f in filenames:
                    listed_files.append(os.path.relpath(os.path.join(dirpath, f), root))
    else:
        listed_files = listed.splitlines()
    out = []
    for f in listed_files:
        f = norm_path(f)
        if not f.endswith(exts) or f.endswith(".d.ts"):
            continue
        if any(fnmatch.fnmatch(f, pat) for pat in fmap.exclude):
            continue
        if os.path.isfile(os.path.join(root, f)):
            out.append(f)
    return sorted(set(out))


TS_SPEC = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*|^\s*import\s+)["']([^"'\n]+)["']""", re.M)
TS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
TS_LINE_COMMENT = re.compile(r"^\s*//.*$", re.M)


def ts_edges(root, files, fmap):
    known = set(files)
    edges = []
    for f in files:
        text = TS_LINE_COMMENT.sub("", TS_BLOCK_COMMENT.sub("", read(root, f)))
        for spec in TS_SPEC.findall(text):
            target = resolve_ts(f, spec, known, fmap)
            if target and target != f:
                edges.append((f, target, spec))
    return edges


def resolve_ts(src, spec, known, fmap):
    if spec.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(src), spec)).replace("\\", "/")
    else:
        base = None
        for alias, target in sorted(fmap.aliases.items(), key=lambda a: -len(a[0])):
            if spec.startswith(alias):
                base = target + spec[len(alias):]
                break
        if base is None:
            return None
        base = norm_path(base)
    stem = re.sub(r"\.(m|c)?jsx?$", "", base)
    candidates = [base]
    for b in dict.fromkeys([stem, base]):
        candidates += [b + e for e in EXTENSIONS["ts"]]
        candidates += [b + "/index" + e for e in EXTENSIONS["ts"]]
    for c in candidates:
        if c in known:
            return c
    return None


SWIFT_DECL = re.compile(
    r"^((?:(?:@\w+(?:\([^)]*\))?|public|internal|open|final|private|fileprivate|package|indirect|nonisolated)\s+)*)"
    r"(?:struct|class|enum|protocol|actor|typealias)\s+(\w+)", re.M)
IDENT = re.compile(r"[A-Za-z_]\w*")


def strip_swift(src):
    out = []
    i, n = 0, len(src)
    while i < n:
        two = src[i:i + 2]
        if two == "//":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if two == "/*":
            depth = 1
            i += 2
            while i < n and depth:
                if src[i:i + 2] == "/*":
                    depth += 1
                    i += 2
                elif src[i:i + 2] == "*/":
                    depth -= 1
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
                out.append("\n" * src[i:k].count("\n"))
                i = k
                continue
        out.append(src[i])
        i += 1
    return "".join(out)


def swift_edges(root, files, fmap):
    stripped = {f: strip_swift(read(root, f)) for f in files}
    owner = {}
    clash = set()
    for f, text in stripped.items():
        for mods, name in SWIFT_DECL.findall(text):
            if "private" in mods.split() or "fileprivate" in mods.split():
                continue
            if name in owner and owner[name] != f:
                clash.add(name)
            owner.setdefault(name, f)
    for name in clash:
        owner.pop(name, None)
    edges = []
    for f, text in stripped.items():
        seen = set()
        for tok in IDENT.findall(text):
            target = owner.get(tok)
            if target and target != f and (target, tok) not in seen:
                seen.add((target, tok))
                edges.append((f, target, tok))
    return edges


def violation(rule, file, target, detail):
    return {"rule": rule, "key": f"{rule}|{file}|{target}", "file": file, "target": target, "detail": detail}


def evaluate_rules(files, edges, fmap):
    found = {r: {} for r in RULES}
    for f in files:
        if fmap.unit_of(f) is None:
            v = violation("placement", f, "", "not in any feature, the kernel or the shell")
            found["placement"][v["key"]] = v
    unit_edges = defaultdict(set)
    path_edges = defaultdict(set)
    for src, dst, detail in edges:
        su, du = fmap.unit_of(src), fmap.unit_of(dst)
        if not su or not du or su == du:
            continue
        (skind, sname), (dkind, dname) = su, du
        if dkind == "shell" and skind != "shell":
            v = violation("uses-shell", src, dst, f"{sname} -> shell ({detail})")
            found["uses-shell"].setdefault(v["key"], v)
        if skind == "kernel" and dkind == "feature":
            v = violation("kernel-uses-feature", src, dname, f"kernel -> {dname} ({detail})")
            found["kernel-uses-feature"].setdefault(v["key"], v)
        if skind == "feature" and dkind == "feature":
            unit_edges[sname].add(dname)
            path_edges[fmap.unit_path(src)[0]].add(dname)
            if not fmap.may_use(src, dname):
                v = violation("unlisted-edge", src, dname, f"{sname} -> {dname} ({detail})")
                found["unlisted-edge"].setdefault(v["key"], v)
            if fmap.language == "ts" and not fmap.is_public(dst, dname):
                v = violation("deep-import", src, dst, f"{sname} -> {dname} internals ({detail})")
                found["deep-import"].setdefault(v["key"], v)
    for a, targets in unit_edges.items():
        for b in targets:
            if a < b and a in unit_edges.get(b, set()):
                v = violation("two-cycle", a, b, f"{a} <-> {b}")
                found["two-cycle"][v["key"]] = v
    return found, unit_edges, path_edges


NOISE_LINE = re.compile(r"^[\s\[\](){};,]*$")
IMPORT_LINE = re.compile(r"^(import\b|export \* from|export \{[^}]*\} from|@testable import|\} from )")
COMMENT_LINE = re.compile(r"^(//|/\*|\*)")


def duplication(root, files, fmap, window):
    by_key = defaultdict(list)
    for f in files:
        unit = fmap.unit_of(f)
        if not unit or unit[0] != "feature":
            continue
        lines = []
        for no, raw in enumerate(read(root, f).splitlines(), 1):
            line = re.sub(r"\s+", " ", raw.strip())
            if not line or NOISE_LINE.match(line) or IMPORT_LINE.match(line) or COMMENT_LINE.match(line):
                continue
            lines.append((no, line))
        for i in range(len(lines) - window + 1):
            chunk = lines[i:i + window]
            by_key[tuple(l for _, l in chunk)].append((f, unit[1], [no for no, _ in chunk]))
    marked = set()
    pairs = defaultdict(set)
    for occurrences in by_key.values():
        if len({feature for _, feature, _ in occurrences}) < 2:
            continue
        for f, _, nos in occurrences:
            marked.update((f, no) for no in nos)
        for i, (fa, ua, na) in enumerate(occurrences):
            for fb, ub, nb in occurrences[i + 1:]:
                if ua != ub:
                    a, b = sorted([fa, fb])
                    pairs[(a, b)].update(na if a == fa else nb)
    top = sorted(pairs.items(), key=lambda kv: -len(kv[1]))[:20]
    return len(marked), [{"files": list(k), "lines": len(v)} for k, v in top]


def measure_ratchets(root, files, edges, fmap):
    out = {}
    cfg = fmap.ratchets
    if cfg.get("shared-single-user", "off") != "off":
        users = defaultdict(set)
        for src, dst, _ in edges:
            su = fmap.unit_of(src)
            if su and src != dst:
                users[dst].add(su)
        items = []
        for f in files:
            u = fmap.unit_of(f)
            if not u or u[0] != "kernel":
                continue
            us = users.get(f, set())
            feature_users = {name for kind, name in us if kind == "feature"}
            other = {kind for kind, _ in us if kind != "feature"}
            if len(feature_users) == 1 and not other:
                items.append({"file": f, "feature": next(iter(feature_users))})
        out["shared-single-user"] = {"value": len(items), "items": items}
    kind_files = cfg.get("kind-files", [])
    if kind_files:
        out["kind-files"] = {"value": {p: len(read(root, p).splitlines()) for p in kind_files}}
    if cfg.get("cross-feature-duplication", "off") != "off":
        window = int(cfg.get("duplication-window", 6))
        value, pairs = duplication(root, files, fmap, window)
        out["cross-feature-duplication"] = {"value": value, "pairs": pairs}
    return out


def measure(root, fmap):
    files = source_files(root, fmap)
    edges = ts_edges(root, files, fmap) if fmap.language == "ts" else swift_edges(root, files, fmap)
    found, unit_edges, path_edges = evaluate_rules(files, edges, fmap)
    ratchets = measure_ratchets(root, files, edges, fmap)
    units = defaultdict(lambda: {"kind": "", "files": 0, "lines": 0})
    for f in files:
        u = fmap.unit_of(f)
        key = u[1] if u else "(unplaced)"
        units[key]["kind"] = u[0] if u else "unplaced"
        units[key]["files"] += 1
        units[key]["lines"] += len(read(root, f).splitlines())
    return {
        "language": fmap.language,
        "files": len(files),
        "units": dict(sorted(units.items())),
        "feature_edges": {a: sorted(b) for a, b in sorted(unit_edges.items())},
        "path_edges": {p: sorted(b) for p, b in sorted(path_edges.items())},
        "violations": {r: sorted(found[r].values(), key=lambda v: v["key"]) for r in RULES},
        "ratchets": ratchets,
    }


def ratchet_values(ratchets):
    return {k: v["value"] for k, v in ratchets.items()}


def compare_ratchet(name, current, recorded, problems):
    if isinstance(current, dict):
        for path, value in current.items():
            compare_ratchet(f"{name} {path}", value, (recorded or {}).get(path), problems)
        return
    base_name = name.split(" ")[0]
    if recorded is None:
        problems.append(f"ratchet: [{name}] has no baseline number. Run check.py --write-baseline")
    elif current > recorded:
        problems.append(f"ratchet: [{name}] {current} > baseline {recorded} — fix: {RATCHET_FIX[base_name]}")
    elif current < recorded:
        problems.append(f"ratchet: [{name}] improved to {current} (baseline {recorded}). Lock it in: run check.py --write-baseline")


def check(report, fmap, baseline, base_baseline, base_config):
    problems = []
    known = set(baseline.get("known", []))
    current_keys = set()
    for rule in RULES:
        mode = fmap.rules[rule]
        for v in report["violations"][rule]:
            current_keys.add(v["key"])
            if mode == "off":
                continue
            if mode == "strict" or v["key"] not in known:
                where = v["file"] if rule != "two-cycle" else "features"
                problems.append(f"{where}: [{rule}] {v['detail']} — fix: {FIX[rule]}")
    for key in sorted(known):
        rule = key.split("|", 1)[0]
        if rule not in RULES:
            problems.append(f"baseline: [unknown-rule] {key}. Remove it")
        elif fmap.rules[rule] == "strict":
            problems.append(f"baseline: [stale] {key}: the rule is strict now. Remove it (run check.py --write-baseline)")
        elif key not in current_keys and fmap.rules[rule] == "baseline":
            problems.append(f"baseline: [stale] {key} no longer occurs. Remove it (run check.py --write-baseline)")
    recorded = baseline.get("ratchets", {})
    for name, value in ratchet_values(report["ratchets"]).items():
        compare_ratchet(name, value, recorded.get(name), problems)
    warnings = []
    if base_baseline is not None:
        for key in sorted(known - set(base_baseline.get("known", []))):
            problems.append(f"baseline: [grew] {key} was added — fix the violation instead of recording it")
        base_r = base_baseline.get("ratchets", {})
        for name, value in recorded.items():
            grew = (isinstance(value, dict) and any(v > (base_r.get(name) or {}).get(p, v) for p, v in value.items())) or (
                not isinstance(value, dict) and name in base_r and value > base_r[name])
            if grew:
                problems.append(f"baseline: [grew] ratchet {name} was raised above the base branch's number")
    if base_config is not None:
        order = {m: i for i, m in enumerate(MODES)}
        for rule in RULES:
            before = base_config.get("rules", {}).get(rule, "strict")
            if order.get(fmap.rules[rule], 0) < order.get(before, 0):
                warnings.append(f"config: rule {rule} loosened from {before} to {fmap.rules[rule]}")
    return problems, warnings


def write_baseline(path, report, fmap):
    known = sorted(v["key"] for r in RULES if fmap.rules[r] == "baseline" for v in report["violations"][r])
    data = {"known": known, "ratchets": ratchet_values(report["ratchets"])}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return data


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
        print(f"group-by-feature: no config at {config_path}", file=sys.stderr)
        return 2
    fmap = FeatureMap(load_json(config_path))
    report = measure(root, fmap)

    if args.report:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.write_baseline:
        data = write_baseline(baseline_path, report, fmap)
        print(f"group-by-feature: wrote {os.path.relpath(baseline_path, root)} "
              f"({len(data['known'])} known violations, ratchets {json.dumps(data['ratchets'], sort_keys=True)})")
        return 0

    baseline = load_json(baseline_path) if os.path.isfile(baseline_path) else {}
    base_baseline = base_config = None
    if args.base:
        base_baseline = at_ref(root, args.base, os.path.relpath(baseline_path, root))
        base_config = at_ref(root, args.base, os.path.relpath(config_path, root))
    problems, warnings = check(report, fmap, baseline, base_baseline, base_config)
    for w in warnings:
        print(f"warning: {w}")
    if problems:
        print(f"group-by-feature: {len(problems)} problem(s)")
        for p in problems:
            print(f"  {p}")
        return 1
    left = len(baseline.get("known", []))
    print(f"group-by-feature: ok ({left} known violation(s) left, ratchets "
          f"{json.dumps(ratchet_values(report['ratchets']), sort_keys=True)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
