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

CFG = {"roots": ["src", "App"], "exclude": ["*.test.*"], "rules": {r: "baseline" for r in check.RULES}}


def write_repo(files):
    root = tempfile.mkdtemp()
    for rel, text in files.items():
        os.makedirs(os.path.join(root, os.path.dirname(rel)), exist_ok=True)
        with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)
    return root


def found(files, cfg=CFG):
    report = check.measure(write_repo(files), check.Config(cfg))
    return {r: [(v["file"], v["line"], v["kind"]) for v in report["violations"][r]] for r in check.RULES}


class TypeScriptCatches(unittest.TestCase):
    def test_only_a_catch_holding_nothing_but_comments_counts(self):
        out = found({"src/a.ts": "try { a(); } catch {}\n"
                                 "try { a(); } catch (e) {\n  // nothing to recover\n}\n"
                                 "p.catch(() => {});\n"
                                 "try { a(); } catch { /* ignore */ }\n"})
        self.assertEqual(out["empty-catch"], [("src/a.ts", 2, "catch"), ("src/a.ts", 6, "catch")])

    def test_handlers_that_do_something_do_not_count(self):
        out = found({"src/a.ts": 'try { a(); } catch (e) { log.error("a.failed", { e }); }\n'
                                 "try { a(); } catch { return undefined; }\n"
                                 "p.catch(report);\n"
                                 'const s = "catch { /* x */ }";\n'
                                 "test.tests.test.test.catch.catch;\n"})
        self.assertEqual(out["empty-catch"], [])


class Swift(unittest.TestCase):
    def test_each_swift_rule(self):
        out = found({"App/Feed/Model.swift":
                     "do { try a() } catch {}\n"
                     "do { try a() } catch let e as DecodingError {\n  // ignored\n}\n"
                     "try? await auth.signOut()\n"
                     "_ = try? store.save()\n"
                     "try? await Task.sleep(nanoseconds: 1)\n"
                     "let v = try? decode(data)\n"
                     "let d = try! JSONDecoder().decode(T.self, from: x)\n"
                     "Task {\n  try await refresh()\n}\n"
                     "Task { @MainActor in\n  do { try await refresh() } catch { log.error(error) }\n}\n"
                     "let t = Task { try await refresh() }\n"
                     'let s = "try! catch {}"\n'})
        self.assertEqual(out["empty-catch"], [("App/Feed/Model.swift", 1, "catch"), ("App/Feed/Model.swift", 2, "catch")])
        self.assertEqual(out["discarded-try"], [("App/Feed/Model.swift", 5, "try? auth.signOut"),
                                                ("App/Feed/Model.swift", 6, "try? store.save")])
        self.assertEqual(out["throwing-task"], [("App/Feed/Model.swift", 10, "Task")])


class Baseline(unittest.TestCase):
    def setUp(self):
        self.files = {"src/a.ts": "try { a(); } catch { /* x */ }\ntry { b(); } catch { /* y */ }\n"}
        self.cfg = check.Config(CFG)

    def run_check(self, files, known, base=None):
        report = check.measure(write_repo(files), self.cfg)
        return check.check(report, self.cfg, {"known": known}, base, None)[0]

    def known(self):
        return [v["key"] for v in check.measure(write_repo(self.files), self.cfg)["violations"]["empty-catch"]]

    def test_known_violations_pass_after_lines_move(self):
        self.assertEqual(self.run_check({"src/a.ts": "\n\ntry { a(); } catch { /* x */ }\nf();\n"
                                                     "try { b(); } catch { /* y */ }\n"}, self.known()), [])

    def test_a_new_violation_fails(self):
        problems = self.run_check({"src/a.ts": self.files["src/a.ts"] + "try { c(); } catch { /* z */ }\n"},
                                  self.known())
        self.assertEqual(len(problems), 1)
        self.assertIn("src/a.ts:3: [empty-catch] catch", problems[0])

    def test_a_fixed_violation_must_leave_the_baseline(self):
        problems = self.run_check({"src/a.ts": "try { a(); } catch { /* x */ }\n"}, self.known())
        self.assertEqual(problems, ["baseline: [stale] empty-catch|src/a.ts|catch #2 no longer occurs. "
                                    "Remove it (run check.py --write-baseline)"])

    def test_a_baseline_that_grew_against_the_base_fails(self):
        problems = self.run_check(self.files, self.known(), base={"known": self.known()[:1]})
        self.assertEqual(len(problems), 1)
        self.assertIn("[grew]", problems[0])

    def test_strict_fails_every_violation(self):
        self.cfg = check.Config(dict(CFG, rules={"empty-catch": "strict"}))
        self.assertEqual(len(self.run_check(self.files, [])), 2)

    def test_an_entry_for_a_rule_lint_now_holds_must_leave_the_baseline(self):
        problems = self.run_check({"src/a.ts": "export {};\n"}, ["floating-void|src/a.ts|void save #1"])
        self.assertEqual(problems, ["baseline: [unknown-rule] floating-void|src/a.ts|void save #1. Remove it"])


class Propose(unittest.TestCase):
    def test_drafts_roots_excludes_and_rule_modes(self):
        root = write_repo({
            "src/routes.ts": "try { a(); } catch { /* ignore */ }\n",
            "src/scripts/seed.ts": "void main();\n",
            "src/routes.test.ts": "void main();\n",
            "client/src/view.ts": "export {};\n",
            "scripts/build.ts": "void main();\n",
        })
        subprocess.run(["git", "init", "-q", root], check=True)
        subprocess.run(["git", "-C", root, "add", "."], check=True)
        out = os.path.join(root, "config.json")
        with contextlib.redirect_stdout(io.StringIO()):
            audit.propose(argparse.Namespace(root=root, out=out))
        cfg = check.load_json(out)
        self.assertEqual(cfg["roots"], ["client", "src"])
        self.assertIn("src/scripts/*", cfg["exclude"])
        self.assertEqual(cfg["rules"], {r: "baseline" if r == "empty-catch" else "strict" for r in check.RULES})


class Lint(unittest.TestCase):
    def test_counts_lint_findings_in_checked_files(self):
        root = write_repo({
            "src/a.ts": "save();\ntry { a(); } catch {}\nif (x) {}\np.catch(() => {});\n"
                        "const b = await r.json<T>();\nload();\n",
            "src/a.test.ts": "save();\n",
            "other/b.ts": "save();\n",
            "App/x.swift": "let d = try! decode()\n",
        })

        def message(rule, line, column, suppression=None):
            m = {"ruleId": rule, "line": line, "column": column}
            if suppression:
                m["suppressions"] = [{"kind": suppression, "justification": ""}]
            return m

        eslint = [
            {"filePath": os.path.join(root, "src/a.ts"),
             "messages": [message("@typescript-eslint/no-floating-promises", 1, 1),
                          message("no-empty", 3, 8), message("no-restricted-syntax", 5, 17)],
             "suppressedMessages": [message("no-empty", 2, 20, "file"), message("no-restricted-syntax", 4, 9, "file"),
                                    message("@typescript-eslint/no-floating-promises", 6, 1, "directive")]},
            {"filePath": os.path.join(root, "src/a.test.ts"),
             "messages": [message("@typescript-eslint/no-floating-promises", 1, 1)]},
            {"filePath": os.path.join(root, "other/b.ts"),
             "messages": [message("@typescript-eslint/no-floating-promises", 1, 1)]},
        ]
        swiftlint = [{"file": os.path.join(root, "App/x.swift"), "line": 1, "character": 9, "rule_id": "force_try"}]
        paths = []
        for name, data in (("eslint.json", eslint), ("swiftlint.json", swiftlint)):
            paths.append(os.path.join(root, name))
            with open(paths[-1], "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        files = set(check.source_files(root, check.Config(CFG)))
        out = [(v["file"], v["line"], v["kind"]) for v in audit.lint_findings(root, files, paths, audit.LINT)]
        self.assertEqual(out, [("App/x.swift", 1, "force-try"), ("src/a.ts", 1, "floating-promise"),
                               ("src/a.ts", 2, "empty-catch"), ("src/a.ts", 4, ".catch")])


if __name__ == "__main__":
    unittest.main()
