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

FILES = {
    "client/projects/list.ts": 'import { conn } from "../connections/conn";\nimport { talk } from "../conversation/talk";\n',
    "client/connections/conn.ts": "export const conn = 1;\n",
    "client/conversation/talk.ts": "export const talk = 1;\n",
    "server/projects/db.ts": 'import { talk } from "../conversation/talk";\n',
    "server/conversation/talk.ts": "export const talk = 1;\n",
}
FEATURES = {
    "connections": {"paths": ["client/connections"]},
    "conversation": {"paths": ["client/conversation", "server/conversation"]},
}


def write_repo(files):
    root = tempfile.mkdtemp()
    for rel, text in files.items():
        os.makedirs(os.path.join(root, os.path.dirname(rel)), exist_ok=True)
        with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)
    return root


def unlisted(root, projects):
    cfg = {"language": "ts", "roots": ["client", "server"], "features": dict(FEATURES, projects=projects)}
    report = check.measure(root, check.FeatureMap(cfg))
    return report, sorted((v["file"], v["target"]) for v in report["violations"]["unlisted-edge"])


class PerPathMayUse(unittest.TestCase):
    def setUp(self):
        self.root = write_repo(FILES)

    def test_string_paths_share_the_feature_list(self):
        report, found = unlisted(self.root, {"paths": ["client/projects", "server/projects"], "may_use": ["connections"]})
        self.assertEqual(found, [("client/projects/list.ts", "conversation"), ("server/projects/db.ts", "conversation")])
        self.assertEqual(report["feature_edges"]["projects"], ["connections", "conversation"])

    def test_path_list_rejects_an_edge_the_other_path_allows(self):
        _, found = unlisted(self.root, {"paths": [
            {"path": "client/projects", "may_use": ["connections"]},
            {"path": "server/projects", "may_use": ["conversation"]},
        ]})
        self.assertEqual(found, [("client/projects/list.ts", "conversation")])

    def test_path_list_replaces_the_feature_list(self):
        _, found = unlisted(self.root, {"may_use": ["connections", "conversation"], "paths": [
            {"path": "client/projects", "may_use": ["connections"]}, "server/projects"]})
        self.assertEqual(found, [("client/projects/list.ts", "conversation")])

    def test_mixed_paths_judge_string_paths_by_the_feature_list(self):
        _, found = unlisted(self.root, {"may_use": ["connections"], "paths": [
            "client/projects", {"path": "server/projects", "may_use": ["conversation"]}]})
        self.assertEqual(found, [("client/projects/list.ts", "conversation")])

    def test_object_path_without_may_use_falls_back(self):
        _, found = unlisted(self.root, {"may_use": ["*"], "paths": [{"path": "client/projects"}, "server/projects"]})
        self.assertEqual(found, [])

    def test_two_cycle_and_edges_span_all_paths(self):
        files = dict(FILES, **{"server/conversation/talk.ts": 'import { db } from "../projects/db";\nexport const talk = 1;\n'})
        root = write_repo(files)
        cfg = {"language": "ts", "roots": ["client", "server"], "features": dict(FEATURES, projects={"paths": [
            {"path": "client/projects", "may_use": ["connections", "conversation"]},
            {"path": "server/projects", "may_use": ["conversation"]},
        ]})}
        cfg["features"]["conversation"] = {"paths": ["client/conversation", "server/conversation"], "may_use": ["projects"]}
        report = check.measure(root, check.FeatureMap(cfg))
        self.assertEqual([v["key"] for v in report["violations"]["two-cycle"]], ["two-cycle|conversation|projects"])
        self.assertEqual(report["feature_edges"]["projects"], ["connections", "conversation"])
        self.assertEqual(report["path_edges"]["client/projects"], ["connections", "conversation"])
        self.assertEqual(report["path_edges"]["server/projects"], ["conversation"])

    def test_bad_entry_is_a_config_error(self):
        for entry in ({"may_use": []}, {"path": "client/projects", "may_use": "connections"}, 3):
            with self.assertRaises(SystemExit):
                check.FeatureMap({"language": "ts", "roots": ["client"], "features": {"projects": {"paths": [entry]}}})


class ProposeDraftsPerPathLists(unittest.TestCase):
    def test_paths_with_different_edges_get_their_own_lists(self):
        root = write_repo({
            "client/src/features/projects/list.ts": 'import { conn } from "../connections/conn";\n',
            "client/src/features/connections/conn.ts": "export const conn = 1;\n",
            "src/projects/db.ts": 'import { talk } from "../conversation/talk";\n',
            "src/conversation/talk.ts": "export const talk = 1;\n",
            "src/billing/pay.ts": 'import { talk } from "../conversation/talk";\n',
            "client/src/features/billing/view.ts": 'import { conn } from "../connections/conn";\n',
        })
        subprocess.run(["git", "init", "-q", root], check=True)
        subprocess.run(["git", "-C", root, "add", "."], check=True)
        out = os.path.join(root, "config.json")
        args = argparse.Namespace(root=root, out=out, language="ts", commits=0)
        with contextlib.redirect_stdout(io.StringIO()):
            audit.propose(args)
        features = check.load_json(out)["features"]
        self.assertEqual(features["projects"]["paths"], [
            {"path": "client/src/features/projects", "may_use": ["connections"]},
            {"path": "src/projects", "may_use": ["conversation"]},
        ])
        self.assertNotIn("may_use", features["projects"])
        self.assertEqual(features["conversation"], {"paths": ["src/conversation"]})
        report = check.measure(root, check.FeatureMap(check.load_json(out)))
        self.assertEqual(report["violations"]["unlisted-edge"], [])


if __name__ == "__main__":
    unittest.main()
