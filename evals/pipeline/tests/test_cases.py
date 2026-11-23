import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import helpers
import grading
import scaffold
import worker_grading

CASES = os.path.join(helpers.ROOT, "cases", "dispatcher")


def grader(case):
    spec = importlib.util.spec_from_file_location("case_grade", os.path.join(CASES, case, "grade.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.grade


class DispatcherCases(unittest.TestCase):
    def test_every_case_builds_its_world_and_fails_when_the_dispatcher_does_nothing(self):
        for case in sorted(os.listdir(CASES)):
            with self.subTest(case=case):
                run_dir = tempfile.mkdtemp(prefix="case-test-")
                try:
                    scaffold.scaffold(os.path.join(CASES, case), run_dir, os.path.join(helpers.ROOT, "fakes"))
                    checks = grader(case)(grading.Run(run_dir))
                    self.assertTrue(checks)
                    self.assertTrue(any(not entry["ok"] for entry in checks))
                finally:
                    shutil.rmtree(run_dir, ignore_errors=True)


class FakeWorker(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="worker-test-")
        self.context = scaffold.scaffold(os.path.join(CASES, "qa-repeat-findings"), self.dir,
                                         os.path.join(helpers.ROOT, "fakes"))
        self.tree = os.path.join(self.context.repo, ".claude", "worktrees", "agent-1")
        self.context.git("worktree", "add", self.tree, "-b", "worktree-agent-1")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def work(self, stage):
        done = subprocess.run(["bash", ".dev/worker.sh", stage, "ACM-70"], cwd=self.tree, capture_output=True, text=True)
        return json.loads(done.stdout.splitlines()[-1])

    def test_a_worker_rehomes_pushes_and_hands_back_its_scripted_verdict(self):
        handback = self.work("qa")
        branch = self.context.tickets["ACM-70"]["branch"]
        run = grading.Run(self.dir)
        self.assertEqual((handback["status"], handback["route"]), ("done", "ready_for_dev"))
        self.assertTrue(handback["produced"].startswith(branch + "@"))
        self.assertEqual(len(run.pushes_to(branch)), 1)
        self.assertEqual(run.stages_run("ACM-70"), ["qa"])

    def test_a_worker_reports_an_error_when_another_worktree_holds_its_branch(self):
        other = os.path.join(self.context.repo, ".claude", "worktrees", "agent-2")
        self.context.git("worktree", "add", other, self.context.tickets["ACM-70"]["branch"])
        self.assertEqual(self.work("qa")["status"], "error")


class GradingHelpers(unittest.TestCase):
    def test_overlap_counts_workers_in_flight_at_once(self):
        run = grading.Run.__new__(grading.Run)
        run.worker_log = [
            {"event": "start", "stage": "dev", "ticket": "A", "index": 0, "epoch": 1},
            {"event": "start", "stage": "dev", "ticket": "B", "index": 0, "epoch": 2},
            {"event": "end", "stage": "dev", "ticket": "A", "index": 0, "epoch": 3, "status": "done"},
            {"event": "start", "stage": "dev", "ticket": "C", "index": 0, "epoch": 3},
            {"event": "end", "stage": "dev", "ticket": "B", "index": 0, "epoch": 5, "status": "done"},
            {"event": "end", "stage": "dev", "ticket": "C", "index": 0, "epoch": 6, "status": "done"},
        ]
        self.assertEqual(run.max_overlap("dev"), 2)

    def test_statuses_seen_drops_repeats_in_a_row(self):
        run = grading.Run.__new__(grading.Run)
        run.linear = {"history": [{"issue": "A", "status": "Spec Done", "labels": []},
                                  {"issue": "A", "status": "Spec Done", "labels": ["in progress"]},
                                  {"issue": "A", "status": "Contract Review", "labels": []}]}
        self.assertEqual(run.statuses_seen("A"), ["Spec Done", "Contract Review"])
        self.assertTrue(run.ever_labelled("A", "in progress"))

    def test_sections_splits_a_document_on_its_second_level_headings(self):
        found = worker_grading.sections("# T\n\n## Behaviors\n\n1. [ ] a\n\n## Modules\n\nm\n")
        self.assertEqual(sorted(found), ["Behaviors", "Modules"])
        self.assertIn("[ ] a", found["Behaviors"])

    def test_dig_walks_objects_and_lists(self):
        body = {"data": [{"title": "a"}, {"title": "b"}]}
        self.assertEqual(worker_grading.dig(body, "data.1.title"), "b")
        self.assertIsNone(worker_grading.dig(body, "data.5.title"))

    def test_handback_is_the_json_object_ending_the_final_message(self):
        run = worker_grading.WorkerRun.__new__(worker_grading.WorkerRun)
        run.events = [{"type": "result", "result": "All done.\n\n{\"status\": \"done\", \"verify\": \"PASS\"}"}]
        self.assertEqual(run.handback(), {"status": "done", "verify": "PASS"})


if __name__ == "__main__":
    unittest.main()


class HiddenTickets(unittest.TestCase):
    def test_a_hidden_seed_ticket_reaches_the_board_only_when_a_worker_reveals_it(self):
        run_dir = tempfile.mkdtemp(prefix="reveal-test-")
        try:
            context = scaffold.scaffold(os.path.join(CASES, "ticket-joins-mid-run"), run_dir,
                                        os.path.join(helpers.ROOT, "fakes"))
            self.assertNotIn("ACM-211", grading.Run(run_dir).linear["issues"])
            tree = os.path.join(context.repo, ".claude", "worktrees", "agent-1")
            context.git("worktree", "add", tree, "-b", "worktree-agent-1")
            done = subprocess.run(["bash", ".dev/worker.sh", "dev", "ACM-210"], cwd=tree, capture_output=True,
                                  text=True)
            self.assertEqual(json.loads(done.stdout.splitlines()[-1])["status"], "done")
            run = grading.Run(run_dir)
            self.assertEqual(run.status("ACM-211"), "Ready for Dev")
            self.assertIsNotNone(run.revealed_at("ACM-211"))
            self.assertEqual(run.stages_run("ACM-210"), ["dev"])
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


class LaneBaseMerge(unittest.TestCase):
    def test_a_stand_in_dev_can_merge_its_conflicting_lane_base_keeping_its_side(self):
        run_dir = tempfile.mkdtemp(prefix="lane-base-test-")
        try:
            context = scaffold.scaffold(os.path.join(CASES, "lane-base-conflict"), run_dir,
                                        os.path.join(helpers.ROOT, "fakes"))
            tree = os.path.join(context.repo, ".claude", "worktrees", "agent-1")
            context.git("worktree", "add", tree, "-b", "worktree-agent-1")
            done = subprocess.run(["bash", ".dev/worker.sh", "dev", "ACM-50"], cwd=tree, capture_output=True,
                                  text=True)
            self.assertEqual(json.loads(done.stdout.splitlines()[-1])["status"], "done")
            run = grading.Run(run_dir)
            branch = context.tickets["ACM-50"]["branch"]
            self.assertTrue(run.merged_into("main", branch))
            self.assertIn("renamed by the ticket", run.origin_file(branch, "src/app.txt"))
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


class WorkerOthers(unittest.TestCase):
    def test_a_worker_case_seeds_other_in_flight_tickets_on_their_own_branches(self):
        import worker_scaffold
        run_dir = tempfile.mkdtemp(prefix="others-test-")
        try:
            world = worker_scaffold.scaffold_worker(
                os.path.join(helpers.ROOT, "cases", "worker", "contract-depends-on"), run_dir,
                os.path.join(helpers.ROOT, "fakes"), run_dir)
            with open(os.path.join(run_dir, "state", "linear.json")) as handle:
                linear = json.load(handle)
            other = linear["issues"]["ACM-206"]
            self.assertEqual(other["status"], "Ready for QA")
            show = lambda path: subprocess.run(
                ["git", "show", "refs/heads/%s:%s" % (other["gitBranchName"], path)], cwd=world["origin"],
                capture_output=True, text=True)
            contract = show("workflows/2026-11-02-acm-206-snooze-a-reminder/contract.md")
            self.assertIn("snoozedUntil", contract.stdout)
            self.assertIn("[x]", contract.stdout)
            self.assertEqual(show("src/reminders/reminder.ts").returncode, 0)
            on_main = subprocess.run(["git", "show", "refs/heads/main:src/reminders/reminder.ts"],
                                     cwd=world["origin"], capture_output=True, text=True).stdout
            self.assertNotIn("snoozedUntil", on_main)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)
