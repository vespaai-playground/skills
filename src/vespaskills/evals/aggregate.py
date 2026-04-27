"""Aggregate grading and timing results into benchmark.json.

Usage:
    vespaskills aggregate --iteration 1
"""

import json
import math
import sys
from pathlib import Path

from vespaskills.evals.config import REPO_ROOT
from vespaskills.logger import get_logger

logger = get_logger()


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


def run(args):
    """Run aggregate command with parsed args."""
    with open(args.evals_json) as f:
        evals_data = json.load(f)

    skill_name = evals_data["skill_name"]
    suffix = getattr(args, "workspace_suffix", "") or ""
    iter_dir = REPO_ROOT / f"{skill_name}-workspace{suffix}" / f"iteration-{args.iteration}"

    if not iter_dir.exists():
        logger.error(f"{iter_dir} not found")
        sys.exit(1)

    usage_keys = (
        "total_input_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    )
    configs: dict[str, dict[str, list]] = {
        "with_skill": {"pass_rate": [], "invoked": [], **{k: [] for k in usage_keys}},
        "without_skill": {"pass_rate": [], "invoked": [], **{k: [] for k in usage_keys}},
    }
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
                configs[run_type]["pass_rate"].append(grading["summary"]["pass_rate"])

            if timing:
                entry["duration_ms"] = timing.get("duration_ms", 0)
                entry["exit_code"] = timing.get("exit_code", -1)
                for key in (*usage_keys, "num_turns", "invoked", "mode"):
                    if key in timing:
                        entry[key] = timing[key]
                for key in usage_keys:
                    if key in timing:
                        configs[run_type][key].append(timing[key])
                if "invoked" in timing:
                    configs[run_type]["invoked"].append(bool(timing["invoked"]))

            per_eval[eval_name][run_type] = entry

    run_summary = {}
    for config_name, metrics in configs.items():
        if not metrics["pass_rate"] and not any(metrics[k] for k in usage_keys):
            continue
        summary_entry = {"eval_count": len(metrics["pass_rate"])}
        if metrics["pass_rate"]:
            summary_entry["pass_rate"] = mean_stddev(metrics["pass_rate"])
        if metrics["invoked"]:
            summary_entry["invocation_rate"] = round(sum(metrics["invoked"]) / len(metrics["invoked"]), 4)
            summary_entry["invoked_count"] = sum(metrics["invoked"])
        for key in usage_keys:
            if metrics[key]:
                summary_entry[key] = mean_stddev(metrics[key])
                summary_entry[f"{key}_total"] = round(sum(metrics[key]), 4)
        run_summary[config_name] = summary_entry

    delta = {}
    if "with_skill" in run_summary and "without_skill" in run_summary:
        w, wo = run_summary["with_skill"], run_summary["without_skill"]
        if "pass_rate" in w and "pass_rate" in wo:
            delta["pass_rate"] = round(w["pass_rate"]["mean"] - wo["pass_rate"]["mean"], 4)
        for key in usage_keys:
            if key in w and key in wo:
                diff = w[key]["mean"] - wo[key]["mean"]
                delta[key] = round(diff, 4)
                if wo[key]["mean"]:
                    delta[f"{key}_pct"] = round(diff / wo[key]["mean"], 4)

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

    logger.info(f"Benchmark: {skill_name} iteration-{args.iteration}")
    logger.info("=" * 60)
    for config_name, stats in run_summary.items():
        logger.info(f"  {config_name}:")
        if "pass_rate" in stats:
            pr = stats["pass_rate"]
            logger.info(f"    pass_rate: {pr['mean']:.1%} +/- {pr['stddev']:.1%}")
        if "invocation_rate" in stats:
            logger.info(
                f"    invocation_rate: {stats['invocation_rate']:.1%} ({stats['invoked_count']}/{stats['eval_count']})"
            )
        for key in usage_keys:
            if key in stats:
                m = stats[key]["mean"]
                total = stats.get(f"{key}_total", 0)
                if key == "cost_usd":
                    logger.info(f"    {key}: ${m:.4f} avg (${total:.4f} total)")
                else:
                    logger.info(f"    {key}: {m:,.0f} avg ({total:,.0f} total)")
    if delta:
        logger.info("  delta (with_skill - without_skill):")
        if "pass_rate" in delta:
            d = delta["pass_rate"]
            sign = "+" if d >= 0 else ""
            logger.info(f"    pass_rate: {sign}{d:.1%}")
        for key in usage_keys:
            if key in delta:
                d = delta[key]
                pct = delta.get(f"{key}_pct")
                sign = "+" if d >= 0 else ""
                pct_str = f" ({sign}{pct:.1%})" if pct is not None else ""
                if key == "cost_usd":
                    logger.info(f"    {key}: {sign}${d:.4f}{pct_str}")
                else:
                    logger.info(f"    {key}: {sign}{d:,.0f}{pct_str}")
    logger.info("Per-eval breakdown:")
    for eval_name, results in per_eval.items():
        parts = []
        for run_type in ("with_skill", "without_skill"):
            if run_type in results:
                r = results[run_type]
                pr = r.get("pass_rate", "?")
                pr_str = f"{pr:.0%}" if isinstance(pr, float) else pr
                parts.append(f"{run_type}={pr_str}")
        logger.info(f"  {eval_name}: {', '.join(parts)}")

    logger.success(f"Saved to: {out_path}")
