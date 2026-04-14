#!/usr/bin/env python3
# ruff: noqa: T201
"""
Aggregate grading and timing results into benchmark.json.

Usage:
    uv run python evals/aggregate.py --iteration 1
"""

import argparse
import json
import math
import sys
from pathlib import Path

from config import EVALS_JSON, REPO_ROOT


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def mean_stddev(values: list[float]) -> dict:
    if not values:
        return {"mean": 0, "stddev": 0}
    n = len(values)
    m = sum(values) / n
    if n < 2:
        return {"mean": round(m, 4), "stddev": 0}
    variance = sum((x - m) ** 2 for x in values) / (n - 1)
    return {"mean": round(m, 4), "stddev": round(math.sqrt(variance), 4)}


def main():
    parser = argparse.ArgumentParser(description="Aggregate eval results into benchmark")
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--evals-json", type=Path, default=EVALS_JSON)
    args = parser.parse_args()

    with open(args.evals_json) as f:
        evals_data = json.load(f)

    skill_name = evals_data["skill_name"]
    iter_dir = REPO_ROOT / f"{skill_name}-workspace" / f"iteration-{args.iteration}"

    if not iter_dir.exists():
        print(f"Error: {iter_dir} not found")
        sys.exit(1)

    configs = {"with_skill": [], "without_skill": []}
    per_eval = {}

    for eval_dir in sorted(iter_dir.iterdir()):
        if not eval_dir.is_dir() or not eval_dir.name.startswith("eval-"):
            continue
        eval_name = eval_dir.name.removeprefix("eval-")
        per_eval[eval_name] = {}

        for run_type in ("with_skill", "without_skill"):
            run_dir = eval_dir / run_type
            grading = load_json(run_dir / "grading.json")
            timing = load_json(run_dir / "timing.json")

            if not grading and not timing:
                continue

            entry = {}
            if grading:
                entry["pass_rate"] = grading["summary"]["pass_rate"]
                entry["passed"] = grading["summary"]["passed"]
                entry["total"] = grading["summary"]["total"]
                configs[run_type].append(
                    {"eval": eval_name, "pass_rate": grading["summary"]["pass_rate"]}
                )

            if timing:
                entry["duration_ms"] = timing.get("duration_ms", 0)
                entry["exit_code"] = timing.get("exit_code", -1)
                for key in ("input_tokens", "output_tokens", "num_turns", "cost_usd"):
                    if key in timing:
                        entry[key] = timing[key]

            per_eval[eval_name][run_type] = entry

    # Compute aggregate stats per config
    run_summary = {}
    for config_name, entries in configs.items():
        if not entries:
            continue
        pass_rates = [e["pass_rate"] for e in entries]
        run_summary[config_name] = {
            "pass_rate": mean_stddev(pass_rates),
            "eval_count": len(entries),
        }

    # Compute delta
    delta = {}
    if "with_skill" in run_summary and "without_skill" in run_summary:
        delta["pass_rate"] = round(
            run_summary["with_skill"]["pass_rate"]["mean"]
            - run_summary["without_skill"]["pass_rate"]["mean"],
            4,
        )

    benchmark = {
        "skill": skill_name,
        "iteration": args.iteration,
        "run_summary": run_summary,
        "delta": delta,
        "per_eval": per_eval,
    }

    out_path = iter_dir / "benchmark.json"
    with open(out_path, "w") as f:
        json.dump(benchmark, f, indent=2)

    # Print readable summary
    print(f"Benchmark: {skill_name} iteration-{args.iteration}")
    print(f"{'=' * 60}")
    for config_name, stats in run_summary.items():
        pr = stats["pass_rate"]
        print(f"  {config_name}:")
        print(f"    pass_rate: {pr['mean']:.1%} +/- {pr['stddev']:.1%}")
    if delta:
        print(f"  delta:")
        d = delta["pass_rate"]
        sign = "+" if d >= 0 else ""
        print(f"    pass_rate: {sign}{d:.1%}")
    print(f"\nPer-eval breakdown:")
    for eval_name, results in per_eval.items():
        parts = []
        for run_type in ("with_skill", "without_skill"):
            if run_type in results:
                r = results[run_type]
                pr = r.get("pass_rate", "?")
                pr_str = f"{pr:.0%}" if isinstance(pr, float) else pr
                parts.append(f"{run_type}={pr_str}")
        print(f"  {eval_name}: {', '.join(parts)}")

    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
