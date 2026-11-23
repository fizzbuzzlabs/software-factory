import json
import os
import shutil
import tempfile
import unittest

import helpers
import scaffold


class FakeBoards(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="fakes-test-")
        case = os.path.join(helpers.ROOT, "cases", "dispatcher", "blocked-by-pooled")
        self.context = scaffold.scaffold(case, self.dir, os.path.join(helpers.ROOT, "fakes"))
        with open(os.path.join(self.dir, "mcp.json")) as handle:
            servers = json.load(handle)["mcpServers"]
        self.linear_env = servers["linear"]["env"]
        self.github_env = servers["github"]["env"]

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def linear(self, name, **arguments):
        return helpers.call("linear_mcp.py", self.linear_env, name, arguments)

    def github(self, name, **arguments):
        return helpers.call("github_mcp.py", self.github_env, name, arguments)

    def test_lists_issues_by_status_name_and_by_status_type(self):
        _, by_name = self.linear("list_issues", team="Acme", state="Ready for Dev")
        _, by_type = self.linear("list_issues", team="Acme", state="started")
        self.assertEqual(sorted(issue["id"] for issue in by_name["issues"]), ["ACM-31", "ACM-32"])
        self.assertEqual(len(by_type["issues"]), 3)

    def test_returns_only_the_fields_asked_for(self):
        _, listed = self.linear("list_issues", team="Acme", state="Ready for QA", fields=["title", "parentId"])
        self.assertEqual(sorted(listed["issues"][0]), ["id", "parentId", "title"])

    def test_shows_blockers_only_when_relations_are_asked_for(self):
        _, plain = self.linear("get_issue", id="ACM-31")
        _, related = self.linear("get_issue", id="ACM-31", includeRelations=True)
        self.assertNotIn("relations", plain)
        self.assertEqual([entry["id"] for entry in related["relations"]["blockedBy"]], ["ACM-30"])

    def test_labels_replaces_the_set_and_add_labels_appends(self):
        self.linear("save_issue", id="ACM-32", labels=["in progress"])
        _, after_replace = self.linear("get_issue", id="ACM-32")
        self.linear("save_issue", id="ACM-32", addLabels=["needs attention"])
        _, after_add = self.linear("get_issue", id="ACM-32")
        self.assertEqual(after_replace["labels"], ["in progress"])
        self.assertEqual(after_add["labels"], ["in progress", "needs attention"])

    def test_rejects_a_status_or_label_the_team_does_not_have(self):
        bad_status, _ = self.linear("save_issue", id="ACM-30", state="Shipped")
        bad_label, _ = self.linear("save_issue", id="ACM-30", labels=["urgent-ish"])
        self.assertTrue(bad_status)
        self.assertTrue(bad_label)

    def test_creates_an_issue_when_no_id_is_given(self):
        _, created = self.linear("save_issue", team="Acme", title="Review pool", state="In Review",
                                 labels=["review-pool"], description="Pool PR: pending\n\n---\nfooter")
        self.assertEqual(created["id"], "ACM-900")
        self.assertEqual(created["status"], "In Review")

    def test_patch_edits_the_description_and_refuses_an_anchor_that_matches_twice(self):
        self.linear("save_issue", team="Acme", title="Review", description="top\n\n---\nfooter")
        self.linear("save_issue", id="ACM-900", patch=[{"op": "insert_before", "anchor": "---", "text": "block\n\n"}])
        self.linear("save_issue", id="ACM-900",
                    patch=[{"op": "replace_range", "from": "top", "to": "block", "new_string": "new top\n\n"}])
        _, issue = self.linear("get_issue", id="ACM-900")
        twice, _ = self.linear("save_issue", id="ACM-900",
                               patch=[{"op": "replace", "old_string": "o", "new_string": "0"}])
        self.assertEqual(issue["description"], "new top\n\nblock\n\n---\nfooter")
        self.assertTrue(twice)

    def test_a_malformed_patch_is_an_error_not_a_crash(self):
        failed, message = self.linear("save_issue", id="ACM-30", patch=[{"op": "replace_range", "start": "a"}])
        self.assertTrue(failed)
        self.assertIn("missing", message)

    def test_comments_are_listed_newest_first(self):
        self.linear("save_comment", issueId="ACM-30", body="first")
        self.linear("save_comment", issueId="ACM-30", body="second")
        _, listed = self.linear("list_comments", issueId="ACM-30")
        self.assertEqual(len(listed["comments"]), 2)

    def test_a_pull_request_needs_a_pushed_head_with_commits_and_no_open_twin(self):
        branch = self.context.tickets["ACM-30"]["branch"]
        missing, _ = self.github("create_pull_request", owner="acme-labs", repo="sample-app", title="x",
                                 head="no-such-branch", base="main")
        empty, _ = self.github("create_pull_request", owner="acme-labs", repo="sample-app", title="x",
                               head="main", base="main")
        failed, opened = self.github("create_pull_request", owner="acme-labs", repo="sample-app", title="x",
                                     head=branch, base="main", draft=True)
        twin, _ = self.github("create_pull_request", owner="acme-labs", repo="sample-app", title="x",
                              head="acme-labs:" + branch, base="main")
        self.assertTrue(missing)
        self.assertTrue(empty)
        self.assertFalse(failed)
        self.assertEqual((opened["number"], opened["draft"], opened["head"]["ref"]), (1, True, branch))
        self.assertTrue(twin)

    def test_pull_requests_filter_by_head_with_or_without_the_owner(self):
        branch = self.context.tickets["ACM-30"]["branch"]
        self.github("create_pull_request", owner="acme-labs", repo="sample-app", title="x", head=branch, base="main")
        _, bare = self.github("list_pull_requests", owner="acme-labs", repo="sample-app", head=branch)
        _, owned = self.github("list_pull_requests", owner="acme-labs", repo="sample-app", head="acme-labs:" + branch)
        self.assertEqual((len(bare), len(owned)), (1, 1))

    def test_merging_is_refused(self):
        failed, _ = self.github("merge_pull_request", owner="acme-labs", repo="sample-app", pullNumber=1)
        self.assertTrue(failed)

    def test_another_repository_is_not_found(self):
        failed, _ = self.github("list_pull_requests", owner="someone", repo="else")
        self.assertTrue(failed)


if __name__ == "__main__":
    unittest.main()
