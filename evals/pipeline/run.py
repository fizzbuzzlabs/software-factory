#!/usr/bin/env python3
"""Run pipeline eval cases against one arm and grade each run.

    run.py --arm main --model claude-fable-5-2                 every dispatcher case, 3 runs each
    run.py --arm main --model claude-opus-5-5 --case 'epic-*' --runs 1
    run.py --arm lean-dispatcher --model claude-fable-5-2 --jobs 4

Build the arm first with build_arm.py. Each run gets its own throwaway world under the work
directory (EVAL_WORK_DIR, else the system temp dir); what's worth keeping is copied to
results/<label>/<arm>/<model>/<case>/<n>/: transcript, usage, grades and the fake boards.
"""

import argparse
import concurrent.futures
import fnmatch
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))

import e2e_grading
import e2e_scaffold
import grading
import scaffold
import worker_grading
import worker_scaffold

LIMIT = threading.Event()

# A headless session waits only 10 minutes for a background worker before killing it and exiting.
# A dispatcher in an interactive session has no such ceiling, so lift it to match.
BG_WAIT_MS = 6 * 60 * 60 * 1000


def hit_limit(result):
    """True when a session ended on the account's usage limit instead of doing the work."""
    text = str(result.get("result", "")).lower()
    return result.get("api_error_status") == 429 or "hit your session limit" in text or "usage limit" in text


KEPT_ENV = ["HOME", "PATH", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG", "LC_ALL", "TERM"]


def clean_env(run_dir):
    """A child session sees none of this session's tokens, MCP settings or Claude Code state."""
    env = {name: os.environ[name] for name in KEPT_ENV if name in os.environ}
    env["GH_CONFIG_DIR"] = os.path.join(run_dir, "gh-config")
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"] = str(BG_WAIT_MS)
    return env


def usage_of(result):
    models = {}
    for model, used in (result.get("modelUsage") or {}).items():
        models[model] = {
            "input": used.get("inputTokens", 0), "output": used.get("outputTokens", 0),
            "cache_read": used.get("cacheReadInputTokens", 0),
            "cache_write": used.get("cacheCreationInputTokens", 0), "cost_usd": used.get("costUSD", 0),
        }
    return {
        "cost_usd": result.get("total_cost_usd"), "turns": result.get("num_turns"),
        "duration_s": round((result.get("duration_ms") or 0) / 1000, 1), "models": models,
        "subagents": result.get("subagent_stats"), "terminal_reason": result.get("terminal_reason"),
        "is_error": result.get("is_error"), "permission_denials": len(result.get("permission_denials") or []),
    }


def load_grader(case_dir):
    spec = importlib.util.spec_from_file_location("case_grade", os.path.join(case_dir, "grade.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.grade


def launch(command, cwd, run_dir, timeout):
    """Run one headless session to the end, or kill it at the timeout. Returns (exit code, timed out)."""
    with open(os.path.join(run_dir, "transcript.jsonl"), "w") as stdout, \
            open(os.path.join(run_dir, "stderr.log"), "w") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=clean_env(run_dir), stdout=stdout, stderr=stderr,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            process.wait(timeout=timeout)
            return process.returncode, False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            time.sleep(5)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return None, True


def keep(run_dir, out_dir, summary, options):
    for name in ("transcript.jsonl", "stderr.log", "scenario.json"):
        source = os.path.join(run_dir, name)
        if os.path.exists(source):
            shutil.copy(source, out_dir)
    for name in ("state", "judge"):
        if os.path.isdir(os.path.join(run_dir, name)):
            shutil.copytree(os.path.join(run_dir, name), os.path.join(out_dir, name))
    with open(os.path.join(out_dir, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    if summary["passed"] and not options.keep:
        shutil.rmtree(run_dir, ignore_errors=True)


def run_worker_once(options, case, number):
    """One real agent, one stage, one seeded ticket in the sample app."""
    case_dir = os.path.join(HERE, "cases", "worker", case)
    out_dir = os.path.join(options.results, options.arm, "workers", case, str(number))
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    run_dir = tempfile.mkdtemp(prefix="%s-%s-%d-" % (options.arm, case, number), dir=options.work)
    started = time.time()
    summary = {"case": case, "arm": options.arm, "model": "agent default", "run": number, "run_dir": run_dir,
               "timed_out": False, "usage": {}}
    try:
        plugin = os.path.join(HERE, ".arms", options.arm, "real-workers")
        world = worker_scaffold.scaffold_worker(case_dir, run_dir, os.path.join(HERE, "fakes"), plugin)
        with open(os.path.join(world["repo"], ".claude", "settings.json")) as handle:
            allowed = json.load(handle)["permissions"]
        settings = os.path.join(run_dir, "settings.json")
        with open(settings, "w") as handle:
            json.dump({"permissions": allowed}, handle)
        command = [
            "claude", "-p", world["brief"], "--agent", "software-factory:" + world["stage"],
            "--plugin-dir", plugin, "--mcp-config", os.path.join(run_dir, "mcp.json"), "--strict-mcp-config",
            "--setting-sources", "project,local", "--settings", settings,
            "--permission-mode", options.permission_mode, "--output-format", "stream-json", "--verbose",
        ]
        timeout = 60 * world["case"].get("timeout_minutes", 90)
        if LIMIT.is_set():
            raise RuntimeError("skipped: the account's usage limit was hit earlier in this run")
        code, timed_out = launch(command, world["tree"], run_dir, timeout)
        run = worker_grading.WorkerRun(run_dir, case_dir)
        if hit_limit(run.result()):
            LIMIT.set()
            raise RuntimeError("the account's usage limit was hit: " + str(run.result().get("result"))[:120])
        try:
            checks = load_grader(case_dir)(run)
        except Exception as error:
            checks = [grading.check("grader ran", False, repr(error))]
        if timed_out:
            checks.append(grading.check("finished inside %d minutes" % (timeout // 60), False, "timed out"))
        summary.update({"passed": all(entry["ok"] for entry in checks), "checks": checks,
                        "usage": usage_of(run.result()), "timed_out": timed_out, "handback": run.handback()})
    except Exception as error:
        summary.update({"passed": False, "void": True,
                        "checks": [grading.check("harness ran", False, repr(error))]})
    summary["wall_s"] = round(time.time() - started, 1)
    keep(run_dir, out_dir, summary, options)
    return summary


def run_e2e_once(options, case, number):
    """The whole pipeline, with real workers, on a real ticket replayed in a sandbox clone of its app repo."""
    case_dir = os.path.join(HERE, "cases", "e2e", case)
    out_dir = os.path.join(options.results, options.arm, "e2e", case, str(number))
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    run_dir = tempfile.mkdtemp(prefix="%s-%s-%d-" % (options.arm, case, number), dir=options.work)
    started = time.time()
    summary = {"case": case, "arm": options.arm, "model": "e2e · " + options.model, "run": number,
               "run_dir": run_dir, "timed_out": False, "usage": {}}
    try:
        world = e2e_scaffold.scaffold_e2e(case_dir, run_dir, os.path.join(HERE, "fakes"))
        settings = os.path.join(run_dir, "settings.json")
        with open(settings, "w") as handle:
            json.dump({"permissions": {"allow": world["allowed"]},
                       "enabledPlugins": {"software-factory@software-factory": False}}, handle)
        ticket = world["case"]["ticket"]["id"]
        command = [
            "claude", "-p", "/factory-pipeline " + ticket,
            "--plugin-dir", os.path.join(HERE, ".arms", options.arm, "real-workers"),
            "--mcp-config", os.path.join(run_dir, "mcp.json"), "--strict-mcp-config",
            "--setting-sources", "project,local", "--settings", settings,
            "--permission-mode", options.permission_mode, "--model", options.model,
            "--max-budget-usd", str(options.budget or world["case"].get("budget_usd", 60)),
            "--output-format", "stream-json", "--verbose",
        ]
        if options.dry:
            raise RuntimeError("dry run: sandbox built at %s, nothing launched" % run_dir)
        if LIMIT.is_set():
            raise RuntimeError("skipped: the account's usage limit was hit earlier in this run")
        timeout = 60 * world["case"].get("timeout_minutes", 300)
        code, timed_out = launch(command, world["repo"], run_dir, timeout)
        result = grading.Run(run_dir).result()
        if hit_limit(result):
            LIMIT.set()
            raise RuntimeError("the account's usage limit was hit: " + str(result.get("result"))[:120])
        try:
            checks, numbers = e2e_grading.grade(run_dir, case_dir, run_gates=not options.no_gates)
        except Exception as error:
            checks, numbers = [grading.check("grader ran", False, repr(error))], {}
        if timed_out:
            checks.append(grading.check("finished inside %d minutes" % (timeout // 60), False, "timed out"))
        summary.update({"passed": all(entry["ok"] for entry in checks), "checks": checks, "numbers": numbers,
                        "usage": usage_of(result), "timed_out": timed_out})
    except Exception as error:
        summary.update({"passed": False, "void": True,
                        "checks": [grading.check("harness ran", False, str(error))]})
    summary["wall_s"] = round(time.time() - started, 1)
    keep(run_dir, out_dir, summary, options)
    return summary


def run_once(options, case, number):
    case_dir = os.path.join(HERE, "cases", options.suite, case)
    out_dir = os.path.join(options.results, options.arm, options.model, case, str(number))
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    run_dir = tempfile.mkdtemp(prefix="%s-%s-%d-" % (options.arm, case, number), dir=options.work)
    started = time.time()
    try:
        context = scaffold.scaffold(case_dir, run_dir, os.path.join(HERE, "fakes"))
        seed = context.seed
        with open(os.path.join(context.repo, ".claude", "settings.json")) as handle:
            allowed = json.load(handle)["permissions"]
        settings = os.path.join(run_dir, "settings.json")
        with open(settings, "w") as handle:
            json.dump({"permissions": allowed}, handle)
        command = [
            "claude", "-p", seed.get("prompt", "/factory-pipeline"),
            "--plugin-dir", os.path.join(HERE, ".arms", options.arm, "fake-workers"),
            "--mcp-config", os.path.join(run_dir, "mcp.json"), "--strict-mcp-config",
            "--setting-sources", "project,local", "--settings", settings,
            "--permission-mode", options.permission_mode,
            "--model", options.model, "--output-format", "stream-json", "--verbose",
        ]
        if options.effort:
            command += ["--effort", options.effort]
        if LIMIT.is_set():
            raise RuntimeError("skipped: the account's usage limit was hit earlier in this run")
        timeout = 60 * seed.get("timeout_minutes", 30)
        transcript = os.path.join(run_dir, "transcript.jsonl")
        with open(transcript, "w") as stdout, open(os.path.join(run_dir, "stderr.log"), "w") as stderr:
            process = subprocess.Popen(command, cwd=context.repo, env=clean_env(run_dir), stdout=stdout,
                                       stderr=stderr, stdin=subprocess.DEVNULL, start_new_session=True)
            timed_out = False
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                time.sleep(5)
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        run = grading.Run(run_dir)
        if hit_limit(run.result()):
            LIMIT.set()
            raise RuntimeError("the account's usage limit was hit: " + str(run.result().get("result"))[:120])
        try:
            checks = load_grader(case_dir)(run)
        except Exception as error:
            checks = [grading.check("grader ran", False, repr(error))]
        if timed_out:
            checks.append(grading.check("finished inside %d minutes" % (timeout // 60), False, "timed out"))
        elif not run.result():
            checks.append(grading.check("session produced a result", False, "exit code %s" % process.returncode))
        summary = {
            "case": case, "arm": options.arm, "model": options.model, "run": number,
            "passed": all(entry["ok"] for entry in checks), "checks": checks,
            "usage": usage_of(run.result()), "wall_s": round(time.time() - started, 1),
            "timed_out": timed_out, "run_dir": run_dir,
        }
    except Exception as error:
        summary = {"case": case, "arm": options.arm, "model": options.model, "run": number, "passed": False,
                   "void": True, "checks": [grading.check("harness ran", False, repr(error))], "usage": {},
                   "wall_s": round(time.time() - started, 1), "timed_out": False, "run_dir": run_dir}

    for name in ("transcript.jsonl", "stderr.log", "scenario.json"):
        source = os.path.join(run_dir, name)
        if os.path.exists(source):
            shutil.copy(source, out_dir)
    if os.path.isdir(os.path.join(run_dir, "state")):
        shutil.copytree(os.path.join(run_dir, "state"), os.path.join(out_dir, "state"))
    with open(os.path.join(out_dir, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    if summary["passed"] and not options.keep:
        shutil.rmtree(run_dir, ignore_errors=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arm", required=True, help="arm name, as built by build_arm.py")
    parser.add_argument("--model", help="dispatcher suite: the model that drives the session, e.g. "
                                        "claude-fable-5-2. Worker cases use each agent's own model")
    parser.add_argument("--suite", default="dispatcher", choices=["dispatcher", "worker", "e2e"])
    parser.add_argument("--budget", type=float, help="e2e: spending cap per run in dollars (default: the case's)")
    parser.add_argument("--dry", action="store_true", help="e2e: build the sandbox and stop before any model call")
    parser.add_argument("--no-gates", action="store_true", help="e2e: skip the app's own gates when grading")
    parser.add_argument("--case", default="*", help="glob over case names")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=3, help="runs in flight at once")
    parser.add_argument("--effort", default=None, help="effort level for the session (default: the CLI's)")
    parser.add_argument("--permission-mode", default="auto")
    parser.add_argument("--label", default=time.strftime("%Y%m%d-%H%M%S"), help="results folder name")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway world of passing runs too")
    options = parser.parse_args()

    if options.suite != "worker" and not options.model:
        parser.error("the %s suite needs --model" % options.suite)
    marker = "seed.json" if options.suite == "dispatcher" else "case.json"
    runner = {"dispatcher": run_once, "worker": run_worker_once, "e2e": run_e2e_once}[options.suite]
    if options.suite == "e2e":
        options.keep = True
    arm_dir = os.path.join(HERE, ".arms", options.arm)
    if not os.path.isdir(arm_dir):
        parser.error("no arm at %s; build it with build_arm.py" % arm_dir)
    options.work = os.environ.get("EVAL_WORK_DIR") or os.path.join(tempfile.gettempdir(), "factory-pipeline-evals")
    os.makedirs(options.work, exist_ok=True)
    options.results = os.path.join(HERE, "results", options.label)
    cases_dir = os.path.join(HERE, "cases", options.suite)
    cases = sorted(name for name in os.listdir(cases_dir)
                   if fnmatch.fnmatch(name, options.case) and os.path.exists(os.path.join(cases_dir, name, marker)))
    if not cases:
        parser.error("no case matches %r" % options.case)

    jobs = [(case, number) for case in cases for number in range(1, options.runs + 1)]
    print("%d runs: %d cases x %d, arm %s, model %s -> %s"
          % (len(jobs), len(cases), options.runs, options.arm, options.model, options.results), flush=True)
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=options.jobs) as pool:
        futures = [pool.submit(runner, options, case, number) for case, number in jobs]
        for future in concurrent.futures.as_completed(futures):
            summary = future.result()
            failed = [entry for entry in summary["checks"] if not entry["ok"]]
            failures += bool(failed)
            usage = summary.get("usage") or {}
            print("%s %s #%d  %ss  $%s  %s turns" % ("PASS" if not failed else "FAIL", summary["case"],
                                                     summary["run"], summary["wall_s"],
                                                     round(usage.get("cost_usd") or 0, 2), usage.get("turns")),
                  flush=True)
            for entry in failed:
                print("     x %s: %s" % (entry["name"], entry["detail"][:300]), flush=True)
            if failed:
                print("     kept: %s" % summary["run_dir"], flush=True)
    if LIMIT.is_set():
        print("STOPPED: the account's usage limit was hit. Runs after that point are void; run again later.",
              flush=True)
        sys.exit(3)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
