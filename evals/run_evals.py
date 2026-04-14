#!/usr/bin/env python3
# ruff: noqa: T201
"""
Run skill evaluations: execute a coding agent with and without skills,
capture outputs, and organize results into workspace directories.

Usage:
    # Run all evals
    uv run python evals/run_evals.py

    # Run a specific eval
    uv run python evals/run_evals.py --eval fix-subtle-bugs

    # Override model
    uv run python evals/run_evals.py --model claude-sonnet-4-20250514

    # Skip baseline
    uv run python evals/run_evals.py --skip-baseline

    # Specify iteration
    uv run python evals/run_evals.py --iteration 2
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from config import EVALS_JSON, REPO_ROOT
from providers import get_provider


def load_evals(evals_path: Path, eval_name: str | None = None) -> dict:
    """Load eval definitions from evals.json."""
    with open(evals_path) as f:
        data = json.load(f)
    if eval_name:
        data["evals"] = [e for e in data["evals"] if e["name"] == eval_name]
        if not data["evals"]:
            print(f"Error: no eval found with name '{eval_name}'")
            sys.exit(1)
    return data


def get_next_iteration(workspace: Path) -> int:
    """Find the next iteration number."""
    if not workspace.exists():
        return 1
    existing = [
        int(d.name.split("-")[1])
        for d in workspace.iterdir()
        if d.is_dir() and d.name.startswith("iteration-")
    ]
    return max(existing, default=0) + 1


def save_outputs(work_dir: Path, dest_dir: Path, exclude_prefixes: list[str] | None = None):
    """Copy output files from work_dir to dest_dir/outputs/."""
    exclude = exclude_prefixes or []
    outputs_dir = dest_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    for f in work_dir.rglob("*"):
        if f.is_file() and not f.is_symlink() and f.name not in (".DS_Store",):
            rel = f.relative_to(work_dir)
            if any(str(rel).startswith(prefix) for prefix in exclude):
                continue
            dest = outputs_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)


def run_single_eval(
    eval_def: dict,
    skill_path: Path | None,
    eval_dir: Path,
    run_type: str,
    provider,
) -> dict:
    """Run a single eval trial and save results."""
    run_dir = eval_dir / run_type
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"    [{run_type}] Running ({provider.name})...")

    # Read skill content if needed
    skill_content = None
    if skill_path and run_type == "with_skill":
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            skill_content = skill_md.read_text()

    with tempfile.TemporaryDirectory(prefix="vespa-eval-") as tmp:
        work_dir = Path(tmp)

        # Copy any fixture files
        for fixture in eval_def.get("files", []):
            src = Path(fixture)
            if src.exists():
                dest = work_dir / src.name
                shutil.copy2(src, dest)

        # Run the agent
        result = provider.run_prompt(
            prompt=eval_def["prompt"],
            work_dir=work_dir,
            skill_content=skill_content,
        )

        # Save outputs
        save_outputs(work_dir, run_dir)

    # Save timing
    usage = provider.extract_usage(result.stdout)
    timing = {
        "provider": provider.name,
        "model": provider.model or "(default)",
        "duration_ms": result.duration_ms,
        "exit_code": result.exit_code,
        **usage,
    }
    with open(run_dir / "timing.json", "w") as f:
        json.dump(timing, f, indent=2)

    # Save raw transcript
    with open(run_dir / "transcript.json", "w") as f:
        f.write(result.stdout or "{}")

    # Save stderr for debugging
    if result.stderr:
        with open(run_dir / "stderr.txt", "w") as f:
            f.write(result.stderr)

    status = "ok" if result.exit_code == 0 else "error"
    print(f"    [{run_type}] {status} ({result.duration_ms}ms, {len(result.output_files)} files)")
    return timing


def main():
    parser = argparse.ArgumentParser(description="Run skill evaluations")
    parser.add_argument("--eval", type=str, help="Run specific eval by name")
    parser.add_argument("--iteration", type=int, help="Iteration number (default: auto)")
    parser.add_argument("--skip-baseline", action="store_true", help="Skip without-skill runs")
    parser.add_argument("--skip-with-skill", action="store_true", help="Skip with-skill runs")
    parser.add_argument("--evals-json", type=Path, default=EVALS_JSON, help="Path to evals.json")
    parser.add_argument("--model", type=str, help="Model override")
    args = parser.parse_args()

    provider = get_provider(model=args.model)

    # Load evals
    evals_data = load_evals(args.evals_json, args.eval)
    skill_name = evals_data["skill_name"]
    skill_path = REPO_ROOT / evals_data["skill_path"]

    if not skill_path.exists():
        print(f"Error: skill path not found: {skill_path}")
        sys.exit(1)

    # Set up workspace
    workspace = REPO_ROOT / f"{skill_name}-workspace"
    iteration = args.iteration or get_next_iteration(workspace)
    iter_dir = workspace / f"iteration-{iteration}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    print(f"Skill: {skill_name}")
    print(f"Provider: {provider.name}")
    print(f"Model: {provider.model or '(default)'}")
    print(f"Workspace: {iter_dir}")
    print(f"Evals: {len(evals_data['evals'])}")
    print()

    all_timings = {}

    for eval_def in evals_data["evals"]:
        eval_name = eval_def["name"]
        eval_dir = iter_dir / f"eval-{eval_name}"
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Write eval metadata
        metadata = {
            "eval_id": eval_def["id"],
            "eval_name": eval_name,
            "prompt": eval_def["prompt"],
            "expected_output": eval_def["expected_output"],
            "assertions": eval_def.get("assertions", []),
        }
        with open(eval_dir / "eval_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"  [{eval_name}]")
        timings = {}

        if not args.skip_with_skill:
            timings["with_skill"] = run_single_eval(
                eval_def, skill_path, eval_dir, "with_skill", provider
            )

        if not args.skip_baseline:
            timings["without_skill"] = run_single_eval(
                eval_def, None, eval_dir, "without_skill", provider
            )

        all_timings[eval_name] = timings
        print()

    # Write summary
    summary = {
        "skill": skill_name,
        "iteration": iteration,
        "provider": provider.name,
        "model": provider.model or "(default)",
        "eval_count": len(evals_data["evals"]),
        "timings": all_timings,
    }
    with open(iter_dir / "run_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Done. Results in: {iter_dir}")
    print(f"\nNext steps:")
    print(f"  1. Review outputs in {iter_dir}/eval-*/{{with,without}}_skill/outputs/")
    print(f"  2. Draft assertions based on what you see")
    print(f"  3. Run: uv run python evals/grade.py --iteration {iteration}")
    print(f"  4. Run: uv run python evals/aggregate.py --iteration {iteration}")


if __name__ == "__main__":
    main()
