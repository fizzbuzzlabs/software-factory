#!/usr/bin/env python3
"""Compare eval results across arms and models.

    compare.py                         every result under results/
    compare.py grid-1 grid-2           only these result labels
    compare.py --json out.json         also write the table as data

One column per cell (arm + model, or arm + "workers"), one row per case: passes/runs, then the
median cost, turns and wall time of a run. A totals row sums every run in the cell, and splits
tokens by model so the driver's usage is separate from the workers'.
"""

import argparse
import fnmatch
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(labels):
    root = os.path.join(HERE, "results")
    runs = []
    for label in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if labels and label not in labels:
            continue
        for directory, _, files in os.walk(os.path.join(root, label)):
            if "summary.json" in files:
                with open(os.path.join(directory, "summary.json")) as handle:
                    summary = json.load(handle)
                if summary.get("void"):
                    continue
                summary["label"] = label
                summary["cell"] = "%s / %s" % (summary["arm"], summary.get("model") or "workers")
                if summary.get("model") == "agent default":
                    summary["cell"] = "%s / workers" % summary["arm"]
                if str(summary.get("model", "")).startswith("e2e"):
                    summary["cell"] = "%s / %s" % (summary["arm"], summary["model"])
                runs.append(summary)
    return runs


def median(values):
    values = [value for value in values if value is not None]
    return statistics.median(values) if values else None


def summarise(runs):
    cells = sorted({run["cell"] for run in runs})
    cases = sorted({run["case"] for run in runs})
    table = {"cells": cells, "cases": {}, "totals": {}, "failures": {}}
    for case in cases:
        table["cases"][case] = {}
        for cell in cells:
            mine = [run for run in runs if run["case"] == case and run["cell"] == cell]
            if not mine:
                continue
            table["cases"][case][cell] = {
                "passed": sum(1 for run in mine if run["passed"]), "runs": len(mine),
                "cost_usd": median([(run.get("usage") or {}).get("cost_usd") for run in mine]),
                "turns": median([(run.get("usage") or {}).get("turns") for run in mine]),
                "wall_s": median([run.get("wall_s") for run in mine]),
            }
            failed = {}
            for run in mine:
                for entry in run["checks"]:
                    if not entry["ok"]:
                        failed[entry["name"]] = failed.get(entry["name"], 0) + 1
            if failed:
                table["failures"].setdefault(case, {})[cell] = failed
    for cell in cells:
        mine = [run for run in runs if run["cell"] == cell]
        models = {}
        for run in mine:
            for model, used in ((run.get("usage") or {}).get("models") or {}).items():
                total = models.setdefault(model, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
                                                  "cost_usd": 0})
                for key in total:
                    total[key] += used.get(key) or 0
        table["totals"][cell] = {
            "runs": len(mine), "passed": sum(1 for run in mine if run["passed"]),
            "cases_all_green": sum(1 for case in cases if table["cases"][case].get(cell)
                                   and table["cases"][case][cell]["passed"] == table["cases"][case][cell]["runs"]),
            "cases": sum(1 for case in cases if table["cases"][case].get(cell)),
            "cost_usd": sum((run.get("usage") or {}).get("cost_usd") or 0 for run in mine),
            "wall_s": sum(run.get("wall_s") or 0 for run in mine), "models": models,
        }
    return table


def by_principle(runs):
    """For each principle in principles.json and each cell, how many of its checks passed across all runs."""
    with open(os.path.join(HERE, "principles.json")) as handle:
        principles = json.load(handle)
    table = {}
    for name, entry in principles.items():
        for run in runs:
            for item in run["checks"]:
                if any(fnmatch.fnmatch(run["case"], case) and needle in item["name"] for case, needle in entry["checks"]):
                    tally = table.setdefault(name, {}).setdefault(run["cell"], {"passed": 0, "checks": 0})
                    tally["checks"] += 1
                    tally["passed"] += bool(item["ok"])
    return table


def show(table):
    cells = table["cells"]
    width = max([len(case) for case in table["cases"]] + [10])
    print("%-*s  %s" % (width, "case", "  ".join("%-26s" % cell[:26] for cell in cells)))
    for case, row in table["cases"].items():
        parts = []
        for cell in cells:
            entry = row.get(cell)
            if not entry:
                parts.append("%-26s" % "-")
                continue
            parts.append("%-26s" % ("%d/%d  $%.2f  %st  %ss" % (
                entry["passed"], entry["runs"], entry["cost_usd"] or 0,
                int(entry["turns"]) if entry["turns"] is not None else "?",
                int(entry["wall_s"]) if entry["wall_s"] is not None else "?")))
        print("%-*s  %s" % (width, case, "  ".join(parts)))
    print()
    for cell in cells:
        total = table["totals"][cell]
        print("%s: %d/%d runs passed, %d/%d cases green in every run, $%.2f, %d min of run time"
              % (cell, total["passed"], total["runs"], total["cases_all_green"], total["cases"],
                 total["cost_usd"], total["wall_s"] / 60))
        for model, used in sorted(total["models"].items()):
            print("    %-22s in %7.0fk  out %6.0fk  cache read %8.0fk  cache write %7.0fk  $%.2f"
                  % (model, used["input"] / 1000, used["output"] / 1000, used["cache_read"] / 1000,
                     used["cache_write"] / 1000, used["cost_usd"]))
    if table["failures"]:
        print("\nFailed checks (count of runs):")
        for case, by_cell in table["failures"].items():
            for cell, failed in by_cell.items():
                for name, count in failed.items():
                    print("  %s | %s | %dx %s" % (case, cell, count, name))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("labels", nargs="*", help="result labels to include (default: all)")
    parser.add_argument("--json", help="write the table to this file")
    options = parser.parse_args()
    runs = load(options.labels)
    if not runs:
        sys.exit("no results found")
    table = summarise(runs)
    table["principles"] = by_principle(runs)
    show(table)
    if table["principles"]:
        print("\nPrinciples (checks passed / checks run, across every run):")
        for name, cells in table["principles"].items():
            print("  %-42s %s" % (name, "   ".join("%s %d/%d" % (cell, tally["passed"], tally["checks"])
                                                    for cell, tally in sorted(cells.items()))))
    if options.json:
        with open(options.json, "w") as handle:
            json.dump(table, handle, indent=1)


if __name__ == "__main__":
    main()
