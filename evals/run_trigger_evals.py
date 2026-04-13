#!/usr/bin/env python3
# ruff: noqa: T201
"""
Test whether skills trigger correctly on realistic prompts.

Runs Claude Code with the plugin installed (--verbose --output-format stream-json)
and parses the event stream to detect whether a specific skill was invoked.

Uses a CSV file with columns: id, skill, should_trigger, category, prompt

Usage:
    # Run all trigger evals
    uv run python evals/run_trigger_evals.py

    # Run only for a specific skill
    uv run python evals/run_trigger_evals.py --skill schema-authoring

    # Run a specific test by ID
    uv run python evals/run_trigger_evals.py --id sa-03

    # Multiple trials for reliability (skill-creator recommends 3)
    uv run python evals/run_trigger_evals.py --trials 3
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from config import CLAUDE_CLI, CLAUDE_MODEL, REPO_ROOT

# Map skill names to the patterns that indicate invocation in the event stream.
# Claude Code skills show up as Skill tool_use calls in the stream-json output.
# The "skill" field in the tool_use input contains the skill identifier.
# For plugin skills, this may be a qualified name like "vespa-support:vespa-docs"
# or a SKILL.md that was read from the skill directory.
#
# This mapping lets us define which skill identifiers count as "triggered"
# for each skill we're testing. Multiple identifiers handle cases where
# Claude uses a related skill from the same plugin.
SKILL_TRIGGER_PATTERNS = {
    "schema-authoring": [
        "schema-authoring",
        "schema_authoring",
        "vespa-skills:schema-authoring",
    ],
}


def load_trigger_evals(csv_path: Path, skill: str | None = None, eval_id: str | None = None) -> list[dict]:
    """Load trigger eval cases from CSV, skipping comment lines."""
    cases = []
    with open(csv_path) as f:
        lines = [line for line in f if not line.strip().startswith("#")]
        reader = csv.DictReader(lines)
        for row in reader:
            if skill and row["skill"] != skill:
                continue
            if eval_id and row["id"] != eval_id:
                continue
            row["should_trigger"] = row["should_trigger"].lower() == "true"
            cases.append(row)
    return cases


def parse_triggered_skills(stdout: str) -> list[str]:
    """
    Parse stream-json output to find which skills were invoked.

    Looks for tool_use events where name="Skill" — the input.skill field
    contains the skill identifier that was triggered.

    Also detects Read tool calls targeting SKILL.md files, which indicates
    Claude loaded a skill's content directly.
    """
    triggered = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        if evt.get("type") != "assistant":
            # Also check user messages for skill launch confirmations
            if evt.get("type") == "user":
                msg = evt.get("message", {})
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, str) and "launching skill:" in content.lower():
                            # Extract skill name from "Launching skill: foo"
                            skill_id = content.split(":", 1)[-1].strip()
                            triggered.append(skill_id.lower())
            continue

        msg = evt.get("message", {})
        for block in msg.get("content", []):
            if not isinstance(block, dict):
                continue

            if block.get("type") == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})

                # Skill tool invocation
                if tool_name == "Skill":
                    skill_id = tool_input.get("skill", "")
                    if skill_id:
                        triggered.append(skill_id.lower())

                # Direct Read of a SKILL.md file
                elif tool_name == "Read":
                    file_path = tool_input.get("file_path", "")
                    if "SKILL.md" in file_path:
                        triggered.append(file_path.lower())

    return triggered


def check_skill_triggered(triggered_skills: list[str], skill_name: str) -> tuple[bool, list[str]]:
    """
    Check if any triggered skills match the target skill.

    Returns (triggered: bool, matched_patterns: list[str])
    """
    patterns = SKILL_TRIGGER_PATTERNS.get(skill_name, [skill_name.lower()])
    matched = []

    for triggered in triggered_skills:
        for pattern in patterns:
            if pattern in triggered:
                matched.append(triggered)
                break

    return len(matched) > 0, matched


def run_trigger_test(prompt: str, skill_name: str, timeout: int = 60) -> dict:
    """
    Run Claude with the plugin installed and detect skill triggering
    from the stream-json event output.
    """
    cmd = [
        CLAUDE_CLI,
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", "3",  # Allow enough turns for skill loading + one response
        "--plugin-dir", str(REPO_ROOT),
    ]

    if CLAUDE_MODEL:
        cmd.extend(["--model", CLAUDE_MODEL])

    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        duration_ms = int((time.time() - start) * 1000)

        triggered_skills = parse_triggered_skills(result.stdout)
        triggered, matched = check_skill_triggered(triggered_skills, skill_name)

        return {
            "exit_code": result.returncode,
            "triggered": triggered,
            "triggered_skills": triggered_skills,
            "matched_patterns": matched,
            "duration_ms": duration_ms,
        }

    except subprocess.TimeoutExpired:
        return {
            "exit_code": 124,
            "triggered": False,
            "triggered_skills": [],
            "matched_patterns": [],
            "duration_ms": int((time.time() - start) * 1000),
        }


def main():
    parser = argparse.ArgumentParser(description="Run skill trigger evaluations")
    parser.add_argument("--csv", type=Path, default=REPO_ROOT / "evals" / "trigger_evals.csv")
    parser.add_argument("--skill", type=str, help="Filter by skill name")
    parser.add_argument("--id", type=str, help="Run specific test by ID")
    parser.add_argument("--trials", type=int, default=1, help="Trials per test (default: 1, recommended: 3)")
    parser.add_argument("--timeout", type=int, default=90, help="Timeout per run in seconds")
    args = parser.parse_args()

    cases = load_trigger_evals(args.csv, args.skill, args.id)
    if not cases:
        print("No test cases found.")
        sys.exit(1)

    print(f"Running {len(cases)} trigger evals ({args.trials} trial(s) each)")
    print(f"Model: {CLAUDE_MODEL or '(default)'}")
    print()

    results = []
    correct = 0
    total = 0

    for case in cases:
        case_id = case["id"]
        skill = case["skill"]
        should = case["should_trigger"]
        category = case["category"]
        prompt = case["prompt"]

        trial_results = []
        for trial in range(args.trials):
            r = run_trigger_test(prompt, skill, timeout=args.timeout)
            trial_results.append(r)

        # Majority vote across trials
        trigger_count = sum(1 for r in trial_results if r["triggered"])
        triggered = trigger_count > args.trials / 2

        # Collect all triggered skills across trials
        all_triggered = []
        for r in trial_results:
            all_triggered.extend(r["triggered_skills"])

        # Evaluate correctness
        if should:
            passed = triggered
        else:
            passed = not triggered

        label = "PASS" if passed else "FAIL"
        trigger_str = f"triggered={trigger_count}/{args.trials}"
        expected_str = "should_trigger" if should else "should_NOT_trigger"

        skills_str = f" skills={list(set(all_triggered))}" if all_triggered else ""
        print(f"  [{label}] {case_id} ({category}, {expected_str}): {trigger_str}{skills_str}")
        if not passed:
            print(f"         prompt: {prompt[:80]}...")

        results.append({
            "id": case_id,
            "skill": skill,
            "should_trigger": should,
            "category": category,
            "prompt": prompt,
            "triggered": triggered,
            "trigger_count": trigger_count,
            "trials": args.trials,
            "passed": passed,
            "all_triggered_skills": list(set(all_triggered)),
            "trial_durations_ms": [r["duration_ms"] for r in trial_results],
        })

        if passed:
            correct += 1
        total += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {correct}/{total} passed ({correct / total:.0%})")

    by_category = {}
    for r in results:
        cat = "should_trigger" if r["should_trigger"] else "should_NOT_trigger"
        by_category.setdefault(cat, {"passed": 0, "total": 0})
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1

    for cat, stats in by_category.items():
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({stats['passed'] / stats['total']:.0%})")

    # Save results
    workspace = REPO_ROOT / f"{cases[0]['skill']}-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    out_path = workspace / "trigger_eval_results.json"
    with open(out_path, "w") as f:
        json.dump({"results": results, "summary": {"correct": correct, "total": total}}, f, indent=2)
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
