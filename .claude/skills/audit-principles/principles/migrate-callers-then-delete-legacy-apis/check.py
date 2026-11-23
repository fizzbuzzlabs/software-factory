#!/usr/bin/env python3
"""migrate-callers-then-delete-legacy-apis check: compatibility layers left beside their replacement.

Reads <dir>/config.json (source roots, facades, how strict each rule is) and
<dir>/baseline.json (known violations and caller counts), where <dir> defaults to
controls/migrate-callers-then-delete-legacy-apis. Exit 0 when clean, 1 on any failure,
2 on a usage error.

  check.py                     fail on new violations, stale baseline entries and caller-count changes
  check.py --base origin/main  also fail when the baseline grew compared with that ref
  check.py --write-baseline    record today's violations and caller counts
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

DEFAULT_DIR = "controls/migrate-callers-then-delete-legacy-apis"
EXTENSIONS = {
    "ts": (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"),
    "swift": (".swift",),
}
RULES = ("reexport-shim", "alias-rename", "deprecated", "dual-mount")
MODES = ("off", "baseline", "strict")
RATCHETS = ("callers",)
FACADE_RULES = ("reexport-shim", "alias-rename")
INDEX_FILE = re.compile(r"(^|/)index\.\w+$")
FIX = {
    "reexport-shim": "import the symbol from where it is defined in every caller, then delete this re-export",
    "alias-rename": "rename every caller to the new name, then delete the alias",
    "deprecated": "move the callers to the replacement, then delete the deprecated declaration",
    "dual-mount": "move every client to one prefix, then delete the other mounts",
}
RATCHET_FIX = {
    "callers": "a new caller is on a baselined compatibility layer. Import or call the replacement instead",
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


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def path_matches(rel, pattern):
    pattern = norm_path(pattern)
    return rel == pattern or rel.startswith(pattern + "/") or fnmatch.fnmatch(rel, pattern)


class Config:
    def __init__(self, cfg):
        self.cfg = cfg
        self.language = cfg.get("language")
        if self.language not in EXTENSIONS:
            raise SystemExit(f"config: language must be one of {', '.join(EXTENSIONS)}")
        self.roots = [norm_path(r) for r in cfg.get("roots", [])]
        if not self.roots:
            raise SystemExit("config: roots must list at least one source directory")
        self.caller_roots = [norm_path(r) for r in cfg.get("caller_roots", [])]
        self.exclude = cfg.get("exclude", [])
        self.aliases = {k: norm_path(v) + "/" for k, v in cfg.get("aliases", {}).items()}
        self.mount_methods = cfg.get("mount_methods", ["route"])
        self.facades = []
        for entry in cfg.get("facades", []):
            if isinstance(entry, str):
                self.facades.append((entry, None))
            elif isinstance(entry, dict) and isinstance(entry.get("path"), str) and isinstance(entry.get("symbols"), list):
                self.facades.append((entry["path"], set(entry["symbols"])))
            else:
                raise SystemExit('config: facades entries must be a path or {"path": ..., "symbols": [...]}')
        self.rules = {r: cfg.get("rules", {}).get(r, "strict") for r in RULES}
        for r, m in self.rules.items():
            if m not in MODES:
                raise SystemExit(f"config: rules.{r} must be one of {', '.join(MODES)}")
        self.ratchets = cfg.get("ratchets", {"callers": "on"})

    def is_facade(self, rel, symbol):
        if INDEX_FILE.search(rel):
            return True
        for path, symbols in self.facades:
            if path_matches(rel, path) and (symbols is None or symbol in symbols):
                return True
        return False


def list_files(root, cfg, roots, exclude=True):
    if not roots:
        return []
    exts = EXTENSIONS[cfg.language]
    listed = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--", *roots)
    if listed is None:
        candidates = []
        for r in roots:
            for dirpath, dirnames, filenames in os.walk(os.path.join(root, r)):
                dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git", "dist", "build")]
                for f in filenames:
                    candidates.append(os.path.relpath(os.path.join(dirpath, f), root))
    else:
        candidates = listed.splitlines()
    out = []
    for f in candidates:
        f = norm_path(f)
        if not f.endswith(exts) or f.endswith(".d.ts"):
            continue
        if exclude and any(fnmatch.fnmatch(f, pat) for pat in cfg.exclude):
            continue
        if os.path.isfile(os.path.join(root, f)):
            out.append(f)
    return sorted(set(out))


def violation(rule, file, symbol, detail, callers=None):
    return {"rule": rule, "key": f"{rule}|{file}|{symbol}", "file": file, "symbol": symbol,
            "detail": detail, "callers": sorted(callers) if callers is not None else None}


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


# ---------------------------------------------------------------- TypeScript

TS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
TS_LINE_COMMENT = re.compile(r"(^|[^:\"'`\\])//[^\n]*")
TS_IMPORT = re.compile(
    r"\bimport\s+(type\s+)?(?:(\w+)\s*,?\s*)?(?:\*\s*as\s+(\w+)|\{([^}]*)\})?\s*(?:from\s*)?[\"']([^\"'\n]+)[\"']")
TS_DYNAMIC = re.compile(r"\b(?:import|require)\s*\(\s*[\"']([^\"'\n]+)[\"']\s*\)")
TS_EXPORT_FROM = re.compile(r"\bexport\s+(?:type\s+)?\{([^}]*)\}\s*from\s*[\"']([^\"'\n]+)[\"']")
TS_EXPORT_STAR = re.compile(r"\bexport\s+(?:type\s+)?\*(?:\s+as\s+(\w+))?\s+from\s*[\"']([^\"'\n]+)[\"']")
TS_EXPORT_LIST = re.compile(r"\bexport\s+(?:type\s+)?\{([^}]*)\}(?!\s*from)")
TS_DECL = re.compile(
    r"^\s*(?:export\s+)?(?:declare\s+)?(?:default\s+)?(?:abstract\s+)?(?:async\s+)?"
    r"(?:function\*?|const|let|var|class|interface|type|enum|namespace)\s+(\w+)", re.M)
TS_ALIAS = re.compile(
    r"^export\s+(type|const)\s+(\w+)(<[^>=]*>)?\s*=\s*([A-Z]\w*)(<[^;=]*>)?\s*;?\s*$", re.M)
TS_JSDOC_DEPRECATED = re.compile(r"/\*\*(?:(?!\*/).)*?@deprecated\b(?:(?!\*/).)*?\*/\s*\n?([^\n]*)", re.S)
TS_MEMBER_NAME = re.compile(
    r"^\s*(?:export\s+)?(?:declare\s+)?(?:default\s+)?(?:abstract\s+)?(?:async\s+)?"
    r"(?:(?:readonly|static|public|private|protected|override|get|set)\s+)*"
    r"(?:function\*?\s+|const\s+|let\s+|var\s+|class\s+|interface\s+|type\s+|enum\s+|namespace\s+)?[\"']?([\w$]+)")


def strip_ts(text):
    return TS_LINE_COMMENT.sub(lambda m: m.group(1), TS_BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text))


def split_top(s):
    parts, depth, cur = [], 0, ""
    for c in s:
        if c in "<([{":
            depth += 1
        elif c in ">)]}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def names_in_braces(body):
    """`a, b as c, type d` -> [(local, exported)]."""
    out = []
    for part in split_top(body):
        part = re.sub(r"^type\s+", "", part)
        bits = re.split(r"\s+as\s+", part)
        local = bits[0].strip()
        out.append((local, bits[-1].strip()))
    return out


def resolve_ts(src, spec, known, cfg):
    if spec.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(src), spec)).replace("\\", "/")
    else:
        base = None
        for alias, target in sorted(cfg.aliases.items(), key=lambda a: -len(a[0])):
            if spec.startswith(alias):
                base = norm_path(target + spec[len(alias):])
                break
        if base is None:
            return None
    stem = re.sub(r"\.(m|c)?jsx?$", "", base)
    candidates = [base]
    for b in dict.fromkeys([stem, base]):
        candidates += [b + e for e in EXTENSIONS["ts"]]
        candidates += [b + "/index" + e for e in EXTENSIONS["ts"]]
    for c in candidates:
        if c in known:
            return c
    return None


class TsFile:
    def __init__(self, rel, raw, known, cfg):
        self.rel = rel
        self.raw = raw
        self.text = strip_ts(raw)
        self.declared = set(TS_DECL.findall(self.text))
        self.imports = []
        self.imported = {}
        for m in TS_IMPORT.finditer(self.text):
            default, namespace, braces, spec = m.group(2), m.group(3), m.group(4), m.group(5)
            target = resolve_ts(rel, spec, known, cfg)
            names = set()
            if default:
                names.add("default")
                self.imported[default] = target
            if namespace:
                names.add("*")
                self.imported[namespace] = target
            for local, exported in names_in_braces(braces or ""):
                names.add(local)
                self.imported[exported] = target
            if not (default or namespace or braces):
                names.add("*")
            if target:
                self.imports.append((target, names))
        for m in TS_DYNAMIC.finditer(self.text):
            target = resolve_ts(rel, m.group(1), known, cfg)
            if target:
                self.imports.append((target, {"*"}))
        for m in TS_EXPORT_FROM.finditer(self.text):
            target = resolve_ts(rel, m.group(2), known, cfg)
            if target:
                self.imports.append((target, {local for local, _ in names_in_braces(m.group(1))}))
        for m in TS_EXPORT_STAR.finditer(self.text):
            target = resolve_ts(rel, m.group(2), known, cfg)
            if target:
                self.imports.append((target, {"*"}))

    def in_repo(self, name):
        return name in self.declared or self.imported.get(name) is not None


def ts_callers(files, defining, symbol):
    """Files other than `defining` that import `symbol` (or everything, `*`) from it."""
    own = files[defining].declared
    out = set()
    for rel, f in files.items():
        if rel == defining:
            continue
        for target, names in f.imports:
            if target != defining:
                continue
            if symbol == "*":
                if "*" in names or names - own - {"default"}:
                    out.add(rel)
            elif symbol in names or "*" in names:
                out.add(rel)
    return out


def same_params(params, args):
    """`Old<T> = New<T>` renames; `Old = New<Data>` instantiates New and is a type of its own."""
    names = [re.match(r"\s*(\w+)", p).group(1) for p in split_top((params or "<>")[1:-1])]
    return names == split_top((args or "<>")[1:-1])


def ts_findings(root, cfg, defs, callers_only):
    known = set(defs) | set(callers_only)
    files = {rel: TsFile(rel, read(root, rel), known, cfg) for rel in sorted(known)}
    mount = cfg.mount_methods and re.compile(
        r"\b\w+\.(?:" + "|".join(map(re.escape, cfg.mount_methods)) +
        r")\(\s*[\"'`]([^\"'`]+)[\"'`]\s*,\s*(?:await\s+)?(?:new\s+)?([\w$.]+)")
    found = []
    for rel in defs:
        f = files[rel]
        text = f.text
        for m in TS_EXPORT_FROM.finditer(text):
            source = resolve_ts(rel, m.group(2), known, cfg)
            for local, exported in names_in_braces(m.group(1)) if source else ():
                found.append(("reexport-shim", rel, exported, f"re-exports {local} from {source}"))
        for m in TS_EXPORT_STAR.finditer(text):
            source = resolve_ts(rel, m.group(2), known, cfg)
            if source:
                found.append(("reexport-shim", rel, m.group(1) or "*", f"re-exports everything from {source}"))
        for m in TS_EXPORT_LIST.finditer(text):
            for local, exported in names_in_braces(m.group(1)):
                if local in f.declared:
                    if local != exported:
                        found.append(("alias-rename", rel, exported, f"{exported} is an old name for {local}"))
                elif f.imported.get(local):
                    found.append(("reexport-shim", rel, exported, f"re-exports {local} imported from {f.imported[local]}"))
        for m in TS_ALIAS.finditer(text):
            old, new = m.group(2), m.group(4)
            if old != new and f.in_repo(new) and same_params(m.group(3), m.group(5)):
                found.append(("alias-rename", rel, old, f"{old} is an old name for {new}"))
        seen = defaultdict(int)
        for m in TS_JSDOC_DEPRECATED.finditer(f.raw):
            nm = TS_MEMBER_NAME.match(m.group(1))
            name = nm.group(1) if nm else "?"
            seen[name] += 1
            symbol = name if seen[name] == 1 else f"{name}#{seen[name]}"
            found.append(("deprecated", rel, symbol, f"{name} is marked @deprecated (line {line_of(f.raw, m.start(1))})"))
        if mount:
            prefixes = defaultdict(set)
            for m in mount.finditer(text):
                prefixes[m.group(2)].add(m.group(1))
            for handler, ps in prefixes.items():
                if len(ps) > 1:
                    found.append(("dual-mount", rel, handler, f"{handler} is mounted at {', '.join(sorted(ps))}"))
    out = []
    for rule, rel, symbol, detail in found:
        if rule in ("deprecated", "dual-mount"):
            out.append((rule, rel, symbol, detail, None))
            continue
        callers = ts_callers(files, rel, symbol)
        out.append((rule, rel, symbol, detail, callers))
    return out


# --------------------------------------------------------------------- Swift

SWIFT_DECL = re.compile(
    r"^((?:(?:@\w+(?:\([^)]*\))?|public|internal|open|final|private|fileprivate|package|indirect|nonisolated)\s+)*)"
    r"(?:struct|class|enum|protocol|actor|typealias)\s+(\w+)", re.M)
SWIFT_ALIAS = re.compile(
    r"^(?:(?:public|internal|open|private|fileprivate|package)\s+)?typealias\s+(\w+)(<[^>]*>)?\s*=\s*(\w+)(<[^>]*>)?\s*$",
    re.M)
SWIFT_AVAILABLE = re.compile(r"@available\s*\(([^)]*)\)")
SWIFT_NAME = re.compile(
    r"\s*(?:(?:@\w+(?:\([^)]*\))?|public|internal|open|final|private|fileprivate|package|static|class|override|"
    r"mutating|nonisolated|convenience|required|lazy|weak|unowned|dynamic)\s+)*"
    r"(?:func|var|let|class|struct|enum|protocol|typealias|actor|case|subscript|init)\b\s*(\w*)")
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


def swift_findings(root, cfg, defs, callers_only):
    stripped = {f: strip_swift(read(root, f)) for f in sorted(set(defs) | set(callers_only))}
    declared = {name for f in defs for _, name in SWIFT_DECL.findall(stripped[f])}
    tokens = {f: set(IDENT.findall(t)) for f, t in stripped.items()}
    found = []
    for rel in defs:
        text = stripped[rel]
        for m in SWIFT_ALIAS.finditer(text):
            old, params, new, args = m.groups()
            if old != new and new in declared and same_params(params, args):
                callers = {f for f, toks in tokens.items() if f != rel and old in toks}
                found.append(("alias-rename", rel, old, f"{old} is an old name for {new}", callers))
        seen = defaultdict(int)
        for m in SWIFT_AVAILABLE.finditer(text):
            args = m.group(1)
            if not re.search(r"\bdeprecated\b|\brenamed\s*:|\bobsoleted\s*:", args):
                continue
            nm = SWIFT_NAME.match(text, m.end())
            name = (nm.group(1) or "init") if nm else "?"
            seen[name] += 1
            symbol = name if seen[name] == 1 else f"{name}#{seen[name]}"
            found.append(("deprecated", rel, symbol, f"{name} is marked @available({args.strip()}) (line {line_of(text, m.start())})", None))
    return found


# ------------------------------------------------------------------- measure

def measure(root, cfg):
    defs = list_files(root, cfg, cfg.roots)
    in_defs = set(defs)
    callers_only = [f for f in list_files(root, cfg, cfg.roots + cfg.caller_roots, exclude=False) if f not in in_defs]
    finder = ts_findings if cfg.language == "ts" else swift_findings
    violations = {r: {} for r in RULES}
    unused = []
    for rule, rel, symbol, detail, callers in finder(root, cfg, defs, callers_only):
        if rule in FACADE_RULES and cfg.is_facade(rel, symbol):
            continue
        if callers is not None and not callers:
            unused.append({"rule": rule, "file": rel, "symbol": symbol, "detail": detail})
            continue
        v = violation(rule, rel, symbol, detail if callers is None else f"{detail}; {len(callers)} caller(s)", callers)
        violations[rule].setdefault(v["key"], v)
    lines = sum(read(root, f).count("\n") for f in defs)
    sites = {v["file"] for r in RULES if cfg.rules[r] != "off" for v in violations[r].values()}
    ratchets = {}
    if cfg.ratchets.get("callers", "on") != "off":
        ratchets["callers"] = {"value": {v["key"]: len(v["callers"]) for r in RULES if cfg.rules[r] == "baseline"
                                         for v in violations[r].values() if v["callers"] is not None}}
    return {
        "language": cfg.language,
        "files": len(defs),
        "caller_files": len(callers_only),
        "production_lines": lines,
        "sites": sorted(sites),
        "sites_per_10k_lines": round(len(sites) * 10000 / lines, 2) if lines else 0,
        "violations": {r: sorted(violations[r].values(), key=lambda v: v["key"]) for r in RULES},
        "unused": sorted(unused, key=lambda u: (u["file"], u["symbol"])),
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
                problems.append(f"{v['file']}: [{rule}] {v['detail']} — fix: {FIX[rule]}")
    for key in sorted(known):
        rule = key.split("|", 1)[0]
        if rule not in RULES:
            problems.append(f"baseline: [unknown-rule] {key}. Remove it")
        elif cfg.rules[rule] == "strict":
            problems.append(f"baseline: [stale] {key}: the rule is strict now. Remove it (run check.py --write-baseline)")
        elif key not in current_keys and cfg.rules[rule] == "baseline":
            problems.append(f"baseline: [stale] {key} no longer occurs. Remove it (run check.py --write-baseline)")
    recorded = baseline.get("ratchets", {})
    for name, value in ratchet_values(report["ratchets"]).items():
        if name == "callers":
            value = {k: n for k, n in value.items() if k in known}
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
            if order.get(cfg.rules[rule], 0) < order.get(before, 0):
                warnings.append(f"config: rule {rule} loosened from {before} to {cfg.rules[rule]}")
        added = [f for f in cfg.cfg.get("facades", []) if f not in base_config.get("facades", [])]
        for f in added:
            warnings.append(f"config: facade added: {json.dumps(f)}")
    return problems, warnings


def write_baseline(path, report, cfg):
    known = sorted(v["key"] for r in RULES if cfg.rules[r] == "baseline" for v in report["violations"][r])
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

    name = "migrate-callers"
    root = args.root or (git(".", "rev-parse", "--show-toplevel") or "").strip() or os.getcwd()
    config_path = args.config or os.path.join(root, DEFAULT_DIR, "config.json")
    baseline_path = args.baseline or os.path.join(root, DEFAULT_DIR, "baseline.json")
    if not os.path.isfile(config_path):
        print(f"{name}: no config at {config_path}", file=sys.stderr)
        return 2
    cfg = Config(load_json(config_path))
    report = measure(root, cfg)

    if args.report:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.write_baseline:
        data = write_baseline(baseline_path, report, cfg)
        print(f"{name}: wrote {os.path.relpath(baseline_path, root)} ({len(data['known'])} known violations)")
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
        print(f"{name}: {len(problems)} problem(s)")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"{name}: ok ({len(baseline.get('known', []))} known violation(s) left)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
