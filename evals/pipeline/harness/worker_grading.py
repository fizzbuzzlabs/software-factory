"""What a worker case's grade.py reads: what one real agent pushed, and helpers to check it.

Scripts decide everything they can: the app's own gates, the controls, a replay of each commit,
and hidden requests against the running server. `judge` asks a model only what scripts can't
tell, and never tells it which arm produced the work.
"""

import contextlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from grading import check, read_json, read_lines

CONTROL_FILES = ["eslint.config.ts", "tsconfig.json", "tsconfig.principles.json", "controls", "knip.json",
                 "debt-baseline.json", "vitest.config.ts", "eslint-suppressions.json"]
JUDGE_MODEL = "claude-sonnet-5-5"


class WorkerRun:
    def __init__(self, run_dir, case_dir):
        self.dir = run_dir
        self.case_dir = case_dir
        state = os.path.join(run_dir, "state")
        seeded = read_json(os.path.join(state, "seeded.json"), {})
        self.base = seeded.get("base")
        self.branch = seeded.get("branch")
        self.folder = seeded.get("folder")
        self.ticket = seeded.get("ticket")
        self.stage = seeded.get("stage")
        self.origin = os.path.join(run_dir, "remotes", "acme-labs", "reminders.git")
        self.linear = read_json(os.path.join(state, "linear.json"), {})
        self.linear_calls = read_lines(os.path.join(state, "linear-calls.jsonl"))
        self.github_calls = read_lines(os.path.join(state, "github-calls.jsonl"))
        self.pushes = read_lines(os.path.join(state, "pushes.jsonl"))[seeded.get("pushes", 0):]
        self.events = read_lines(os.path.join(run_dir, "transcript.jsonl"))
        self._checkout = None
        self._installed = False
        self._gates = {}

    def result(self):
        for event in reversed(self.events):
            if event.get("type") == "result":
                return event
        return {}

    def final_message(self):
        return str(self.result().get("result", ""))

    def handback(self):
        """The JSON object the worker ended its final message with, or {} when there is none."""
        for line in reversed(self.final_message().strip().splitlines()):
            line = line.strip().strip("`")
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except ValueError:
                    continue
        match = re.search(r"\{[^{}]*\"status\"[^{}]*\}", self.final_message(), re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except ValueError:
                pass
        return {}

    def sh(self, command, cwd=None, timeout=900, env=None):
        merged = dict(os.environ, CI="1")
        merged.update(env or {})
        try:
            done = subprocess.run(command, cwd=cwd or self.checkout(), capture_output=True, text=True,
                                  timeout=timeout, shell=isinstance(command, str), env=merged)
            return done.returncode, (done.stdout + done.stderr)
        except subprocess.TimeoutExpired:
            return 124, "timed out after %ss" % timeout

    def git(self, *arguments, cwd=None):
        done = subprocess.run(["git"] + list(arguments), cwd=cwd or self.checkout(), capture_output=True, text=True)
        return done.returncode, done.stdout.strip()

    def tip(self):
        done = subprocess.run(["git", "--git-dir", self.origin, "rev-parse", "refs/heads/" + self.branch],
                              capture_output=True, text=True)
        return done.stdout.strip()

    def pushed(self):
        return bool(self.tip()) and self.tip() != self.base

    def checkout(self):
        """A fresh clone of what the worker pushed."""
        if self._checkout is None:
            path = os.path.join(self.dir, "graded")
            shutil.rmtree(path, ignore_errors=True)
            subprocess.run(["git", "clone", "-q", "--branch", self.branch, self.origin, path],
                           capture_output=True, check=True)
            self._checkout = path
        return self._checkout

    def install(self):
        """Install the pushed tree's dependencies, once."""
        if not self._installed:
            self._installed = True
            self.sh(["npm", "ci", "--no-audit", "--no-fund"], cwd=self.checkout())
        return self.checkout()

    def commits(self):
        """Commits the worker added, oldest first: sha, subject, body, files."""
        code, log = self.git("log", "--reverse", "--format=%H%x1f%s%x1f%b%x1e", "%s..HEAD" % self.base)
        found = []
        for record in log.split("\x1e"):
            if not record.strip():
                continue
            sha, subject, body = (record.strip().split("\x1f") + ["", ""])[:3]
            _, names = self.git("show", "--name-only", "--format=", sha)
            found.append({"sha": sha, "subject": subject, "body": body, "files": names.split()})
        return found

    def changed_files(self):
        return self.git("diff", "--name-only", self.base, "HEAD")[1].split()

    def diff(self, *paths):
        return self.git("diff", self.base, "HEAD", "--", *paths)[1]

    def added_lines(self, *paths):
        return [line[1:] for line in self.diff(*paths).splitlines()
                if line.startswith("+") and not line.startswith("+++")]

    def test_changes(self):
        """What the worker did to test files, as a diff, for a judge to read: only added lines are its work."""
        files = [path for path in self.changed_files() if path.endswith(".test.ts")]
        if not files:
            return "(the worker changed no test file)"
        return ("A diff of the test files. Judge only the lines the diff adds (starting with +); the rest was "
                "there before.\n\n" + self.diff(*files))

    def read(self, path):
        full = os.path.join(self.checkout(), path)
        if not os.path.exists(full):
            return None
        with open(full) as handle:
            return handle.read()

    def source(self, suffix=".ts", tests=False):
        """Every source file under src/ as {path: text}; test files only when asked."""
        found = {}
        for directory, _, files in os.walk(os.path.join(self.checkout(), "src")):
            for name in files:
                if not name.endswith(suffix) or (name.endswith(".test.ts") and not tests):
                    continue
                full = os.path.join(directory, name)
                with open(full) as handle:
                    found[os.path.relpath(full, self.checkout())] = handle.read()
        return found

    def gate(self, name):
        """Run one of the app's own gates on the pushed tree, once: typecheck, lint, test, debt:check."""
        if name not in self._gates:
            self.install()
            self._gates[name] = self.sh(["npm", "run", "--silent", name])
        return self._gates[name]

    @contextlib.contextmanager
    def server(self, cwd=None):
        """The app running from the pushed tree on a free port; yields its base URL, or None if it won't boot."""
        process = subprocess.Popen(["npm", "run", "--silent", "start"], cwd=cwd or self.install(),
                                   env=dict(os.environ, PORT="0"), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True)
        url = None
        deadline = time.time() + 40
        try:
            while time.time() < deadline:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue
                match = re.search(r'"port"\s*:\s*(\d+)', line)
                if match and "listening" in line:
                    url = "http://127.0.0.1:" + match.group(1)
                    break
            yield url
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, 15)

    def replay(self, script):
        """Run a hidden request script against the running app. Returns (passed, failures, transcript)."""
        with open(os.path.join(self.case_dir, "hidden", script)) as handle:
            steps = json.load(handle)
        with self.server() as url:
            if url is None:
                return False, ["the server did not boot from the pushed tree"], []
            failures, transcript = run_steps(url, steps)
        return not failures, failures, transcript


def run_steps(url, steps):
    """Send a hidden request script to a running app. Returns (failures, transcript)."""
    failures, transcript, captured = [], [], {}
    for step in steps:
        path = step["path"]
        sent = json.dumps(step.get("body")) if step.get("body") is not None else None
        for key, value in captured.items():
            path = path.replace("{%s}" % key, str(value))
        if sent is not None:
            sent = sent.replace("{in_2s}", instant(2)).replace("{tomorrow}", instant(86400))
            sent = sent.replace("{yesterday}", instant(-86400))
        status, body = request(url + path, step.get("method", "GET"),
                               json.loads(sent) if sent is not None else None, step.get("raw"))
        transcript.append({"request": "%s %s" % (step.get("method", "GET"), path), "status": status, "body": body})
        expect = step.get("expect", {})
        label = step.get("name", "%s %s" % (step.get("method", "GET"), path))
        if "status" in expect and status != expect["status"]:
            failures.append("%s: status %s, expected %s; body %s"
                            % (label, status, expect["status"], json.dumps(body)[:200]))
        for pointer, wanted in (expect.get("json") or {}).items():
            got = dig(body, pointer)
            if got != wanted:
                failures.append("%s: %s is %r, expected %r" % (label, pointer, got, wanted))
        for pointer in expect.get("present", []):
            if dig(body, pointer) is None:
                failures.append("%s: %s is missing" % (label, pointer))
        for pointer in expect.get("absent", []):
            if dig(body, pointer) is not None:
                failures.append("%s: %s should be absent" % (label, pointer))
        for pointer, wanted in (expect.get("length") or {}).items():
            got = dig(body, pointer)
            if not isinstance(got, list) or len(got) != wanted:
                failures.append("%s: %s has length %s, expected %s"
                                % (label, pointer, len(got) if isinstance(got, list) else None, wanted))
        for key, pointer in (step.get("capture") or {}).items():
            captured[key] = dig(body, pointer)
        if step.get("wait_ms"):
            time.sleep(step["wait_ms"] / 1000)
    return failures, transcript


def instant(offset_seconds):
    moment = time.gmtime(time.time() + offset_seconds)
    return time.strftime("%Y-%m-%dT%H:%M:%S", moment) + ".000Z"


def sections(markdown):
    """A markdown document as {heading text: body} for its `## ` sections."""
    found, current = {}, None
    for line in (markdown or "").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            found[current] = ""
        elif current is not None:
            found[current] += line + "\n"
    return found


def dig(body, pointer):
    current = body
    for part in [piece for piece in pointer.split(".") if piece]:
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def request(url, method, body, raw=None):
    data = raw.encode() if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"content-type": "application/json"} if data is not None else {}
    call = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(call, timeout=15) as response:
            status, text = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read().decode()
    except (urllib.error.URLError, OSError) as error:
        return 0, {"transport_error": str(error)}
    try:
        return status, json.loads(text) if text else None
    except ValueError:
        return status, {"unparsed": text[:300]}


def shipped(run):
    """Checks every worker case shares: it pushed, in orchestrator mode, and handed back."""
    writes = [call for call in run.linear_calls if call["tool"] in ("save_issue", "save_comment")]
    pulls = [call for call in run.github_calls if call["tool"] == "create_pull_request"]
    forced = [push for push in run.pushes if push["forced"]]
    elsewhere = [push for push in run.pushes if push["ref"] != "refs/heads/" + run.branch]
    handback = run.handback()
    return [
        check("the session finished on its own", run.result().get("subtype") == "success",
              run.result().get("terminal_reason") or "no result record"),
        check("handed back a status", handback.get("status") in ("done", "blocked", "error"),
              run.final_message()[-300:]),
        check("opened no PR (orchestrator mode)", not pulls),
        check("made no Linear move or comment (orchestrator mode)", not writes,
              [(call["tool"], call["arguments"].get("state")) for call in writes]),
        check("pushed only its ticket branch, never forced", not forced and not elsewhere,
              [push["ref"] for push in forced + elsewhere]),
    ]


def gates(run, names=("typecheck", "lint", "test", "debt:check")):
    """The app's own gates and controls pass on what was pushed, and none was loosened to get there."""
    checks = []
    for name in names:
        code, output = run.gate(name)
        checks.append(check("`npm run %s` passes on the pushed tree" % name, code == 0, output[-700:]))
    loosened = [path for path in run.changed_files()
                if any(path == control or path.startswith(control + "/") for control in CONTROL_FILES)]
    disables = [line.strip() for line in run.added_lines("src", "scripts")
                if re.search(r"eslint-disable|@ts-ignore|@ts-expect-error|@ts-nocheck", line)]
    skipped = [line.strip() for line in run.added_lines("src")
               if re.search(r"\b(it|test|describe)\.(skip|todo|only)\b|\bx(it|describe)\(", line)]
    checks += [
        check("no control, baseline or compiler setting was changed", not loosened, loosened),
        check("no lint or type check was disabled inline", not disables, disables[:5]),
    ]
    return checks, skipped


def replay_commits(run, pattern=r"behavior \d+"):
    """Every commit that claims a behavior leaves typecheck and the tests green on its own."""
    scratch = os.path.join(run.dir, "replay")
    shutil.rmtree(scratch, ignore_errors=True)
    subprocess.run(["git", "clone", "-q", "--branch", run.branch, run.origin, scratch], capture_output=True, check=True)
    shutil.copytree(os.path.join(run.install(), "node_modules"), os.path.join(scratch, "node_modules"),
                    symlinks=True)
    claimed = [commit for commit in run.commits() if re.search(pattern, commit["subject"], re.I)]
    broken = []
    for commit in claimed:
        subprocess.run(["git", "checkout", "-q", commit["sha"]], cwd=scratch, capture_output=True)
        if "package-lock.json" in commit["files"]:
            run.sh(["npm", "ci", "--no-audit", "--no-fund"], cwd=scratch)
        for name in ("typecheck", "test"):
            code, output = run.sh(["npm", "run", "--silent", name], cwd=scratch)
            if code != 0:
                broken.append("%s (%s): %s fails: %s" % (commit["sha"][:8], commit["subject"], name, output[-300:]))
                break
    return claimed, broken


def judge(run, name, rubric, material):
    """Ask a model yes/no questions about the work. Returns {criterion id: (passed, why)}; {} if it failed."""
    prompt = (
        "You are grading a piece of software work against a rubric. Judge only what is in front of you. "
        "Be strict: a criterion passes only when the material clearly meets it.\n\n"
        "## Rubric\n\nEach line is `<id>: <what must be true>`.\n\n%s\n\n## Material\n\n%s\n\n"
        "## Answer\n\nReply with one JSON object and nothing else: "
        "{\"criteria\": [{\"id\": \"<id>\", \"pass\": true|false, \"why\": \"<one sentence, quoting the "
        "material>\"}]} with one entry per rubric line, in order."
    ) % (rubric, material)
    env = {name_: os.environ[name_] for name_ in ("HOME", "PATH", "USER", "TMPDIR", "LANG") if name_ in os.environ}
    scratch = os.path.join(run.dir, "judge")
    os.makedirs(scratch, exist_ok=True)
    try:
        done = subprocess.run(["claude", "-p", prompt, "--model", JUDGE_MODEL, "--output-format", "json",
                               "--setting-sources", "project"],
                              cwd=scratch, env=env, capture_output=True, text=True, timeout=600)
        answer = json.loads(done.stdout).get("result", "")
        parsed = json.loads(re.search(r"\{.*\}", answer, re.S).group(0))
    except (ValueError, AttributeError, subprocess.TimeoutExpired) as error:
        with open(os.path.join(scratch, name + ".error.txt"), "w") as handle:
            handle.write(repr(error))
        return {}
    with open(os.path.join(scratch, name + ".json"), "w") as handle:
        json.dump(parsed, handle, indent=1)
    return {entry["id"]: (bool(entry.get("pass")), entry.get("why", "")) for entry in parsed.get("criteria", [])}


def judged(run, name, rubric, material):
    """Turn a rubric into checks: one per line, failed when the judge could not be reached."""
    verdicts = judge(run, name, rubric, material)
    checks = []
    for line in rubric.strip().splitlines():
        if ":" not in line:
            continue
        identifier, wanted = [part.strip() for part in line.split(":", 1)]
        passed, why = verdicts.get(identifier, (False, "the judge returned no verdict"))
        checks.append(check("judge: " + wanted, passed, why))
    return checks
