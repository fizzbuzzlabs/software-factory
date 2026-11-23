"""Grade one end-to-end run: did the pipeline carry a real ticket to review, and is the work sound?

Three kinds of evidence, most trusted first:
  the boards and branches   where the ticket ended, which stages ran, what is on origin
  the app's own gates       typecheck, lint, debt check and the test suite, on the ticket branch
  a blind judge             each success criterion of the ticket's spec, read against the diff

`measure` returns numbers that aren't pass or fail (rounds, size of the change next to what shipped).
"""

import os
import re
import shutil
import subprocess

import grading
import worker_grading
from grading import check

GATES = ["typecheck", "lint", "debt:check", "test"]
LOOSENED = re.compile(r"(^|/)(eslint\.config\.[a-z]+|tsconfig[^/]*\.json|debt-baseline\.json|eslint-suppressions\.json|"
                      r"knip\.json)$|^controls/.*(baseline|config)\.json$")
DIFF_LIMIT = 60000


class E2ERun(grading.Run):
    def __init__(self, run_dir):
        super().__init__(run_dir)
        self.seeded = grading.read_json(os.path.join(run_dir, "state", "seeded.json"), {})
        self.ticket = self.seeded.get("ticket")
        self.branch = self.seeded.get("branch")
        self.folder = self.seeded.get("folder")
        self._tree = None

    def tree(self):
        """A fresh clone of the ticket branch as the pipeline left it on origin, or None if it's gone."""
        if self._tree is None:
            path = os.path.join(self.dir, "graded")
            shutil.rmtree(path, ignore_errors=True)
            done = subprocess.run(["git", "clone", "-q", "--branch", self.branch, self.origin, path],
                                  capture_output=True, text=True)
            self._tree = path if done.returncode == 0 else ""
        return self._tree or None

    def sh(self, command, timeout=3600):
        try:
            done = subprocess.run(command, cwd=self.tree(), capture_output=True, text=True, timeout=timeout,
                                  env=dict({name: os.environ[name] for name in
                                            ("HOME", "PATH", "USER", "TMPDIR", "LANG", "SHELL")
                                            if name in os.environ}, CI="1"))
            return done.returncode, done.stdout + done.stderr
        except subprocess.TimeoutExpired:
            return 124, "timed out after %ss" % timeout

    def tree_git(self, *arguments):
        done = subprocess.run(["git"] + list(arguments), cwd=self.tree(), capture_output=True, text=True)
        return done.stdout.strip()

    def read(self, path):
        full = os.path.join(self.tree(), path)
        if not os.path.exists(full):
            return ""
        with open(full) as handle:
            return handle.read()

    def stages(self):
        """Every worker the dispatcher launched, in order, as its stage name."""
        return [brief["worker"] for brief in self.briefs() if brief["worker"] in ("architect", "cto", "dev", "qa")]


def failing_files(output):
    """Test files a vitest run reports as failed."""
    plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
    return set(re.findall(r"^\s*(?:FAIL|❯)\s+(\S+\.test\.[a-z]+)", plain, re.M))


def prepare_steps(case_dir):
    """Commands the app's CI runs before its tests, from the case's `before_tests`."""
    case = grading.read_json(os.path.join(case_dir, "case.json"), {})
    return [step.split() for step in case.get("before_tests", [])]


def baseline_failures(run, steps=()):
    """Test files that already fail on the sandbox's main, before the ticket: run once per app commit."""
    cache = os.path.join(os.path.dirname(run.dir), "baseline-%s-%d.json" % (run.seeded["app_base"][:12], len(steps)))
    if os.path.exists(cache):
        return set(grading.read_json(cache, []))
    path = os.path.join(run.dir, "baseline")
    shutil.rmtree(path, ignore_errors=True)
    subprocess.run(["git", "clone", "-q", "--branch", "main", run.origin, path], capture_output=True, check=True)
    env = dict({name: os.environ[name] for name in ("HOME", "PATH", "USER", "TMPDIR", "LANG", "SHELL")
                if name in os.environ}, CI="1")
    subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=path, capture_output=True, env=env, timeout=1800)
    for step in steps:
        subprocess.run(step, cwd=path, capture_output=True, env=env, timeout=1800)
    done = subprocess.run(["npm", "run", "--silent", "test"], cwd=path, capture_output=True, text=True, env=env,
                          timeout=3600)
    failures = sorted(failing_files(done.stdout + done.stderr))
    with open(cache, "w") as handle:
        import json
        json.dump(failures, handle)
    shutil.rmtree(path, ignore_errors=True)
    return set(failures)


def app_diff(app, base, head, stat=False):
    arguments = ["git", "diff", "--shortstat" if stat else "--stat", base, head, "--", ".", ":!workflows"]
    return subprocess.run(arguments, cwd=app, capture_output=True, text=True).stdout.strip()


def measure(run):
    """Numbers for the report: how many times each stage ran, and the change's size next to what shipped."""
    stages = run.stages()
    seeded = run.seeded
    numbers = {"stages": stages, "final_status": run.status(run.ticket), "labels": run.labels(run.ticket),
               "rounds": max(0, stages.count("qa") - 1), "comments": len(run.comments(run.ticket))}
    if run.tree():
        numbers["change"] = run.tree_git("diff", "--shortstat", "origin/main...HEAD", "--", ".", ":!workflows")
        subjects = run.tree_git("log", "--format=%s", "origin/main..HEAD").splitlines()
        numbers["commits"] = len(subjects)
        numbers["behavior_commits"] = len([line for line in subjects if re.search(r"behavior \d+", line, re.I)])
        contract = run.read("workflows/%s/contract.md" % run.folder)
        numbers["behaviors"] = len(re.findall(r"^\s*\d+\.\s*\[[ x]\]", worker_grading.sections(contract)
                                              .get("Behaviors", ""), re.M))
    numbers["shipped_change"] = app_diff(seeded["app"], seeded["app_base"], seeded["app_shipped"], stat=True)
    return numbers


def grade(run_dir, case_dir, run_gates=True):
    run = E2ERun(run_dir)
    ticket = run.ticket
    stages = run.stages()
    first = []
    for stage in stages:
        if stage not in first:
            first.append(stage)
    pool = run.pulls(head="review-pool", base="main", state="open")
    body = pool[0]["body"] if pool else ""
    checks = [
        check("ticket ends In Review", run.status(ticket) == "In Review", run.status(ticket)),
        check("ticket is not left flagged for a human", "needs attention" not in run.labels(ticket),
              run.comments(ticket)[-1][:300] if run.comments(ticket) else ""),
        check("all four stages ran, in order", first == ["architect", "cto", "dev", "qa"], stages),
        check("ticket branch is in the review pool", run.merged_into(run.branch, "review-pool"),
              run.origin_branches()),
        check("one open pool PR that fixes the ticket", len(pool) == 1 and ("Fixes " + ticket) in body, body[:300]),
        check("the pool was verified PASS or SKIP", bool(re.search(r"Verify:\s*(PASS|SKIP)", body)), body[:200]),
    ] + grading.hygiene(run, forced_ok=["review-pool"])

    if not run.tree():
        return checks + [check("the ticket branch is on origin", False, run.origin_branches())], measure(run)

    changed = run.tree_git("diff", "--name-only", "origin/main...HEAD").split()
    loosened = [path for path in changed if LOOSENED.search(path)]
    added = [line[1:] for line in run.tree_git("diff", "origin/main...HEAD", "--", "src", "client", "tests",
                                                "shared", "scripts").splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    disables = [line.strip() for line in added if re.search(r"eslint-disable|@ts-ignore|@ts-expect-error|@ts-nocheck", line)]
    subjects = run.tree_git("log", "--format=%s", "origin/main..HEAD").splitlines()
    behavior_commits = [line for line in subjects if re.search(r"behavior \d+", line, re.I)]
    contract = run.read("workflows/%s/contract.md" % run.folder)
    behaviors = re.findall(r"^\s*\d+\.\s*\[([ x])\]", worker_grading.sections(contract).get("Behaviors", ""), re.M)
    checks += [
        check("contract.md and test-plan.md are on the branch",
              bool(contract) and bool(run.read("workflows/%s/test-plan.md" % run.folder)), changed[:8]),
        check("every contract behavior is ticked", bool(behaviors) and " " not in behaviors, behaviors),
        check("each behavior has its own commit", len(behavior_commits) >= len(behaviors) > 0,
              "%d behavior commits for %d behaviors" % (len(behavior_commits), len(behaviors))),
        check("no control, baseline or compiler setting was changed", not loosened, loosened),
        check("no lint or type check was disabled inline", not disables, disables[:5]),
    ]

    if run_gates:
        code, output = run.sh(["npm", "ci", "--no-audit", "--no-fund"], timeout=1800)
        checks.append(check("dependencies install on the ticket branch", code == 0, output[-400:]))
        for step in prepare_steps(case_dir) if code == 0 else []:
            step_code, step_output = run.sh(step)
            checks.append(check("`%s` succeeds on the ticket branch" % " ".join(step), step_code == 0,
                                step_output[-400:]))
        for gate in GATES if code == 0 else []:
            gate_code, gate_output = run.sh(["npm", "run", "--silent", gate])
            if gate == "test":
                before = baseline_failures(run, prepare_steps(case_dir))
                new = sorted(failing_files(gate_output) - before)
                broke = gate_code != 0 and (new or not failing_files(gate_output))
                checks.append(check("the test suite has no failing file that passed before the ticket", not broke,
                                    "newly failing: %s; already failing before the ticket: %s; %s"
                                    % (new, sorted(before), gate_output[-300:] if broke else "")))
            else:
                checks.append(check("`npm run %s` passes on the ticket branch" % gate, gate_code == 0,
                                    gate_output[-700:]))

    spec = run.read("workflows/%s/spec.md" % run.folder)
    criteria = [line.strip()[2:] for line in worker_grading.sections(spec).get("Success Criteria", "").splitlines()
                if line.strip().startswith("- ")]
    if criteria:
        rubric = "\n".join("criterion-%d: The change does this, and a test in it would fail if it stopped: %s"
                           % (index + 1, text) for index, text in enumerate(criteria))
        diff = run.tree_git("diff", "origin/main...HEAD", "--", ".", ":!workflows", ":!package-lock.json")
        material = ("### The ticket's spec\n\n%s\n\n### The change (a diff; long diffs are cut off)\n\n%s"
                    % (spec, diff[:DIFF_LIMIT]))
        judge_host = worker_grading.WorkerRun.__new__(worker_grading.WorkerRun)
        judge_host.dir = run.dir
        checks += worker_grading.judged(judge_host, "criteria", rubric, material)
    return checks, measure(run)
