#!/usr/bin/env python3
"""Tests for check.py and audit.py propose. Never installed into a repo.

  python3 -I -m unittest discover -s <this folder> -p 'test_*.py'
"""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit
import check


def write_repo(files, root=None):
    root = root or tempfile.mkdtemp()
    for rel, text in files.items():
        path = os.path.join(root, rel)
        if text is None:
            os.remove(path)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return root


def commit(root, message):
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)
    subprocess.run(["git", "-C", root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message], check=True)


def ts_cfg(**extra):
    return dict({"language": "ts", "roots": ["src"], "caller_roots": ["tests"]}, **extra)


def found(root, cfg):
    report = check.measure(root, check.Config(cfg))
    return {r: sorted((v["file"], v["symbol"], len(v["callers"] or [])) for v in vs)
            for r, vs in report["violations"].items() if vs}, report


PROTOCOL = "export interface Deck { id: string }\nexport type Recipe = { name: string };\nexport function load(id: string) { return id; }\n"


class TypeScriptRules(unittest.TestCase):
    def test_reexport_with_callers_is_a_shim(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/deck.ts": 'export type { Deck } from "./protocol";\nexport const local = 1;\n',
            "src/view.ts": 'import type { Deck } from "./deck";\n',
            "tests/view.test.ts": 'import { Deck } from "../src/deck";\n',
        })
        rules, _ = found(root, ts_cfg())
        self.assertEqual(rules, {"reexport-shim": [("src/deck.ts", "Deck", 2)]})

    def test_imported_then_exported_is_a_shim(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/deck.ts": 'import type { Deck } from "./protocol";\nexport type { Deck };\n',
            "src/view.ts": 'import type { Deck } from "./deck";\n',
        })
        rules, _ = found(root, ts_cfg())
        self.assertEqual(rules, {"reexport-shim": [("src/deck.ts", "Deck", 1)]})

    def test_reexport_without_callers_is_unused_not_a_violation(self):
        root = write_repo({"src/protocol.ts": PROTOCOL, "src/deck.ts": 'export type { Deck } from "./protocol";\n'})
        rules, report = found(root, ts_cfg())
        self.assertEqual(rules, {})
        self.assertEqual([(u["file"], u["symbol"]) for u in report["unused"]], [("src/deck.ts", "Deck")])

    def test_callers_through_the_new_home_do_not_count(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/deck.ts": 'export type { Deck } from "./protocol";\n',
            "src/view.ts": 'import type { Deck } from "./protocol";\n',
        })
        self.assertEqual(found(root, ts_cfg())[0], {})

    def test_library_reexport_and_index_barrel_are_facades(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/zod.ts": 'export { z } from "zod";\n',
            "src/feature/index.ts": 'export { load } from "../protocol";\n',
            "src/view.ts": 'import { z } from "./zod";\nimport { load } from "./feature";\n',
        })
        self.assertEqual(found(root, ts_cfg())[0], {})

    def test_configured_facade_exempts_listed_symbols_only(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/store.ts": 'export type { Deck, Recipe } from "./protocol";\n',
            "src/view.ts": 'import type { Deck, Recipe } from "./store";\n',
        })
        rules, _ = found(root, ts_cfg(facades=[{"path": "src/store.ts", "symbols": ["Deck"]}]))
        self.assertEqual(rules, {"reexport-shim": [("src/store.ts", "Recipe", 1)]})
        self.assertEqual(found(root, ts_cfg(facades=["src/store.ts"]))[0], {})

    def test_export_star_counts_names_the_module_does_not_declare(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/old.ts": 'export * from "./protocol";\nexport const mine = 1;\n',
            "src/a.ts": 'import { mine } from "./old";\n',
            "src/b.ts": 'import { load } from "./old";\n',
        })
        rules, _ = found(root, ts_cfg())
        self.assertEqual(rules, {"reexport-shim": [("src/old.ts", "*", 1)]})

    def test_rename_alias_but_not_an_instantiation_or_library_alias(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL + "export type Intent<D> = { data: D };\n",
            "src/recipe.ts": ('import type { Recipe, Intent } from "./protocol";\nimport type { Big } from "lib";\n'
                              "export type CompleteRecipe = Recipe;\nexport type Card = Intent<string>;\n"
                              "export type OldIntent<D> = Intent<D>;\nexport type Huge = Big;\n"),
            "src/view.ts": 'import type { CompleteRecipe, Card, OldIntent, Huge } from "./recipe";\n',
        })
        rules, _ = found(root, ts_cfg())
        self.assertEqual(rules, {"alias-rename": [("src/recipe.ts", "CompleteRecipe", 1), ("src/recipe.ts", "OldIntent", 1)]})

    def test_export_as_rename_of_a_local(self):
        root = write_repo({
            "src/recipe.ts": "export function recipe() { return 1; }\nexport { recipe as oldRecipe };\n",
            "src/view.ts": 'import { oldRecipe } from "./recipe";\n',
        })
        self.assertEqual(found(root, ts_cfg())[0], {"alias-rename": [("src/recipe.ts", "oldRecipe", 1)]})

    def test_deprecated_counts_without_callers(self):
        root = write_repo({"src/api.ts": (
            "/** @deprecated use load */\nexport function fetchIt() {}\n"
            "export interface Row {\n  /**\n   * Old field.\n   * @deprecated\n   */\n  legacyId?: string;\n}\n"
            "/** Not deprecated. */\nexport const fine = 1;\n")})
        self.assertEqual(found(root, ts_cfg())[0], {"deprecated": [("src/api.ts", "fetchIt", 0), ("src/api.ts", "legacyId", 0)]})

    def test_dual_mount(self):
        root = write_repo({"src/server.ts": (
            'app.route("/connect/browsing", createBrowsing(opts));\n'
            'app.route("/connect/browserbase", createBrowsing(opts));\n'
            'app.route("/auth", createAuth(a));\napp.route("/auth", createTour(t));\n'
            'app.use("/a", cors());\napp.use("/b", cors());\n')})
        self.assertEqual(found(root, ts_cfg())[0], {"dual-mount": [("src/server.ts", "createBrowsing", 0)]})
        rules, _ = found(root, ts_cfg(mount_methods=["route", "use"]))
        self.assertEqual(rules, {"dual-mount": [("src/server.ts", "cors", 0), ("src/server.ts", "createBrowsing", 0)]})

    def test_aliases_resolve_callers(self):
        root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/deck.ts": 'export type { Deck } from "@/protocol";\n',
            "src/view.ts": 'import type { Deck } from "@/deck.js";\n',
        })
        rules, _ = found(root, ts_cfg(aliases={"@/": "src/"}))
        self.assertEqual(rules, {"reexport-shim": [("src/deck.ts", "Deck", 1)]})


class SwiftRules(unittest.TestCase):
    def test_deprecated_and_rename_alias(self):
        root = write_repo({
            "App/Model.swift": ("struct Recipe {}\ntypealias CompleteRecipe = Recipe\ntypealias UserID = String\n"
                                "typealias Box<T> = Array<T>\nstruct Holder { typealias Element = Recipe }\n"
                                "@available(*, deprecated, renamed: \"load()\")\nfunc fetch() {}\n"
                                "@available(*, unavailable)\nrequired init?(coder: NSCoder) {}\n"
                                "@available(iOS 17, *)\nfunc modern() {}\n"),
            "App/View.swift": "let r: CompleteRecipe = Recipe()\n// CompleteRecipe in a comment\nlet u: UserID = \"\"\n",
        })
        cfg = {"language": "swift", "roots": ["App"]}
        self.assertEqual(found(root, cfg)[0], {
            "alias-rename": [("App/Model.swift", "CompleteRecipe", 1)],
            "deprecated": [("App/Model.swift", "fetch", 0)],
        })


class Baseline(unittest.TestCase):
    def setUp(self):
        self.root = write_repo({
            "src/protocol.ts": PROTOCOL,
            "src/deck.ts": 'export type { Deck, Recipe } from "./protocol";\n',
            "src/a.ts": 'import type { Deck } from "./deck";\n',
            "src/b.ts": 'import type { Recipe } from "./deck";\n',
        })
        self.cfg = check.Config(ts_cfg(rules={r: "baseline" for r in check.RULES}))
        self.path = os.path.join(self.root, "baseline.json")
        self.baseline = check.write_baseline(self.path, check.measure(self.root, self.cfg), self.cfg)

    def problems(self, base=None):
        return check.check(check.measure(self.root, self.cfg), self.cfg, check.load_json(self.path), base, None)[0]

    def test_recorded_state_passes(self):
        self.assertEqual(self.baseline["known"], ["reexport-shim|src/deck.ts|Deck", "reexport-shim|src/deck.ts|Recipe"])
        self.assertEqual(self.baseline["ratchets"]["callers"], {"reexport-shim|src/deck.ts|Deck": 1, "reexport-shim|src/deck.ts|Recipe": 1})
        self.assertEqual(self.problems(), [])

    def test_new_caller_on_a_baselined_shim_fails(self):
        write_repo({"src/c.ts": 'import type { Deck } from "./deck";\n'}, self.root)
        self.assertEqual(len(self.problems()), 1)
        self.assertIn("2 > baseline 1", self.problems()[0])

    def test_migrated_shim_must_come_off_the_baseline(self):
        write_repo({"src/b.ts": 'import type { Recipe } from "./protocol";\n'}, self.root)
        self.assertEqual(self.problems(), ["baseline: [stale] reexport-shim|src/deck.ts|Recipe no longer occurs. "
                                           "Remove it (run check.py --write-baseline)"])

    def test_new_shim_fails_and_baseline_may_not_grow(self):
        write_repo({"src/old.ts": 'export { load } from "./protocol";\n', "src/c.ts": 'import { load } from "./old";\n'}, self.root)
        self.assertTrue(any("[reexport-shim]" in p for p in self.problems()))
        check.write_baseline(self.path, check.measure(self.root, self.cfg), self.cfg)
        self.assertTrue(any("[grew]" in p for p in self.problems(base=self.baseline)))


class Propose(unittest.TestCase):
    def test_history_splits_moved_symbols_from_facades(self):
        root = write_repo({
            "src/protocol.ts": "export type Other = number;\n",
            "src/deck.ts": "export interface Deck { id: string }\n",
            "src/store.ts": 'export type { Other } from "./protocol";\n',
            "src/scope.ts": "export type Scoped = { org: string };\nexport type Scope = Scoped;\n",
            "src/recipe.ts": "export interface CompleteRecipe { name: string }\n",
            "src/a.ts": ('import type { Deck } from "./deck";\nimport type { Other } from "./store";\n'
                         'import type { Scope } from "./scope";\nimport type { CompleteRecipe } from "./recipe";\n'),
            "tests/a.test.ts": 'import type { Deck } from "../src/deck";\n',
        })
        subprocess.run(["git", "init", "-q", root], check=True)
        commit(root, "start")
        write_repo({
            "src/protocol.ts": "export type Other = number;\nexport interface Deck { id: string }\n",
            "src/deck.ts": 'export type { Deck } from "./protocol";\n',
            "src/recipe.ts": 'import type { Recipe } from "./protocol";\nexport type CompleteRecipe = Recipe;\n',
        }, root)
        write_repo({"src/protocol.ts": "export type Other = number;\nexport interface Deck { id: string }\n"
                                       "export interface Recipe { name: string }\n"}, root)
        commit(root, "ABC-1 define Deck once in protocol")
        out = os.path.join(root, "draft.json")
        args = argparse.Namespace(root=root, out=out, language=None)
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            audit.propose(args)
        cfg = check.load_json(out)
        self.assertEqual(cfg["roots"], ["src"])
        self.assertEqual(cfg["caller_roots"], ["tests"])
        self.assertEqual(cfg["facades"], [{"path": "src/scope.ts", "symbols": ["Scope"]},
                                          {"path": "src/store.ts", "symbols": ["Other"]}])
        self.assertEqual(cfg["rules"]["reexport-shim"], "baseline")
        self.assertEqual(cfg["rules"]["deprecated"], "strict")
        self.assertIn("ABC-1 define Deck once in protocol", printed.getvalue())
        rules, _ = found(root, cfg)
        self.assertEqual(rules, {"alias-rename": [("src/recipe.ts", "CompleteRecipe", 1)],
                                 "reexport-shim": [("src/deck.ts", "Deck", 2)]})


if __name__ == "__main__":
    unittest.main()
