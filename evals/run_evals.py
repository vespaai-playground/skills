#!/usr/bin/env python3
# ruff: noqa: T201
"""
Run skill evaluations: execute Claude CLI with and without skills,
capture outputs, and organize results into workspace directories.

Usage:
    # Run all evals for the default skill (schema-authoring)
    python evals/run_evals.py

    # Run a specific eval by name
    python evals/run_evals.py --eval basic-text-search

    # Run only with-skill (skip baseline)
    python evals/run_evals.py --skip-baseline

    # Run only baseline (skip with-skill)
    python evals/run_evals.py --skip-with-skill

    # Specify iteration number (default: auto-detect next)
    python evals/run_evals.py --iteration 2

    # Override model
    EVAL_MODEL=claude-sonnet-4-20250514 python evals/run_evals.py
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from config import (
    CLAUDE_CLI,
    CLAUDE_MODEL,
    CLAUDE_TIMEOUT,
    EVALS_JSON,
    MAX_TURNS,
    REPO_ROOT,
)


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


def run_claude(
    prompt: str,
    work_dir: Path,
    skill_path: Path | None = None,
    timeout: int = CLAUDE_TIMEOUT,
) -> dict:
    """
    Run Claude CLI on a prompt, optionally with a skill directory available.

    Returns dict with: exit_code, stdout, stderr, duration_ms, output_files
    """
    cmd = [CLAUDE_CLI, "-p", prompt, "--output-format", "json", "--max-turns", str(MAX_TURNS)]

    if CLAUDE_MODEL:
        cmd.extend(["--model", CLAUDE_MODEL])

    # If skill_path provided, make the skill available by symlinking into work_dir
    if skill_path:
        skill_link = work_dir / skill_path.name
        if not skill_link.exists():
            skill_link.symlink_to(skill_path.resolve())
        # Tell Claude about the skill in the prompt prefix
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            skill_content = skill_md.read_text()
            prompt_with_skill = (
                f"You have access to the following skill for reference:\n\n"
                f"<skill path=\"{skill_path.name}/SKILL.md\">\n{skill_content}\n</skill>\n\n"
                f"Use the skill above to help with this task:\n\n{prompt}"
            )
            cmd[2] = prompt_with_skill

    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout + 30,
            env=env,
        )
        duration_ms = int((time.time() - start) * 1000)

        # Collect output files (anything Claude created in work_dir)
        output_files = []
        for f in work_dir.rglob("*"):
            if f.is_file() and not f.is_symlink() and f.name not in (".DS_Store",):
                rel = f.relative_to(work_dir)
                # Skip the symlinked skill directory
                if skill_path and str(rel).startswith(skill_path.name):
                    continue
                output_files.append(str(rel))

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": duration_ms,
            "output_files": output_files,
        }

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "exit_code": 124,
            "stdout": "",
            "stderr": f"Timeout after {timeout}s",
            "duration_ms": duration_ms,
            "output_files": [],
        }


def extract_token_usage(stdout: str) -> dict:
    """Try to extract token usage from Claude CLI JSON output."""
    try:
        data = json.loads(stdout)
        # claude -p --output-format json returns a result object
        usage = {}
        if isinstance(data, dict):
            if "usage" in data:
                usage = data["usage"]
            elif "total_cost_usd" in data:
                usage["cost_usd"] = data["total_cost_usd"]
            if "num_turns" in data:
                usage["num_turns"] = data["num_turns"]
        return usage
    except (json.JSONDecodeError, TypeError):
        return {}


def save_outputs(work_dir: Path, dest_dir: Path, skill_path: Path | None = None):
    """Copy output files from work_dir to dest_dir/outputs/."""
    outputs_dir = dest_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    for f in work_dir.rglob("*"):
        if f.is_file() and not f.is_symlink() and f.name not in (".DS_Store",):
            rel = f.relative_to(work_dir)
            if skill_path and str(rel).startswith(skill_path.name):
                continue
            dest = outputs_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)


def run_single_eval(
    eval_def: dict,
    skill_path: Path | None,
    eval_dir: Path,
    run_type: str,  # "with_skill" or "without_skill"
) -> dict:
    """Run a single eval trial and save results."""
    run_dir = eval_dir / run_type
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"    [{run_type}] Running...")

    with tempfile.TemporaryDirectory(prefix="vespa-eval-") as tmp:
        work_dir = Path(tmp)

        # Copy any fixture files
        for fixture in eval_def.get("files", []):
            src = Path(fixture)
            if src.exists():
                dest = work_dir / src.name
                shutil.copy2(src, dest)

        # Run Claude
        effective_skill = skill_path if run_type == "with_skill" else None
        result = run_claude(
            prompt=eval_def["prompt"],
            work_dir=work_dir,
            skill_path=effective_skill,
        )

        # Save outputs
        save_outputs(work_dir, run_dir, effective_skill)

    # Save timing
    usage = extract_token_usage(result["stdout"])
    timing = {
        "duration_ms": result["duration_ms"],
        "exit_code": result["exit_code"],
        **usage,
    }
    with open(run_dir / "timing.json", "w") as f:
        json.dump(timing, f, indent=2)

    # Save raw transcript (stdout from claude)
    with open(run_dir / "transcript.json", "w") as f:
        f.write(result["stdout"] or "{}")

    # Save stderr for debugging
    if result["stderr"]:
        with open(run_dir / "stderr.txt", "w") as f:
            f.write(result["stderr"])

    status = "ok" if result["exit_code"] == 0 else "error"
    print(f"    [{run_type}] {status} ({result['duration_ms']}ms, {len(result['output_files'])} files)")
    return timing


def main():
    parser = argparse.ArgumentParser(description="Run skill evaluations")
    parser.add_argument("--eval", type=str, help="Run specific eval by name")
    parser.add_argument("--iteration", type=int, help="Iteration number (default: auto)")
    parser.add_argument("--skip-baseline", action="store_true", help="Skip without-skill runs")
    parser.add_argument("--skip-with-skill", action="store_true", help="Skip with-skill runs")
    parser.add_argument("--evals-json", type=Path, default=EVALS_JSON, help="Path to evals.json")
    args = parser.parse_args()

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
    print(f"Skill path: {skill_path}")
    print(f"Workspace: {iter_dir}")
    print(f"Evals: {len(evals_data['evals'])}")
    print(f"Model: {CLAUDE_MODEL or '(default)'}")
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
                eval_def, skill_path, eval_dir, "with_skill"
            )

        if not args.skip_baseline:
            timings["without_skill"] = run_single_eval(
                eval_def, None, eval_dir, "without_skill"
            )

        all_timings[eval_name] = timings
        print()

    # Write summary
    summary = {
        "skill": skill_name,
        "iteration": iteration,
        "model": CLAUDE_MODEL or "(default)",
        "eval_count": len(evals_data["evals"]),
        "timings": all_timings,
    }
    with open(iter_dir / "run_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Done. Results in: {iter_dir}")
    print(f"\nNext steps:")
    print(f"  1. Review outputs in {iter_dir}/eval-*/{{with,without}}_skill/outputs/")
    print(f"  2. Draft assertions based on what you see")
    print(f"  3. Run: python evals/grade.py --iteration {iteration}")
    print(f"  4. Run: python evals/aggregate.py --iteration {iteration}")


if __name__ == "__main__":
    main()
