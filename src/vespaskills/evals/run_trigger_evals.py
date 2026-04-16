"""Test whether skills trigger correctly on realistic prompts.

Runs Claude Code with the plugin installed (--verbose --output-format stream-json)
and parses the event stream to detect whether a specific skill was invoked.

Uses a CSV file with columns: id, skill, should_trigger, category, prompt

Usage:
    vespaskills trigger
    vespaskills trigger --skill schema-authoring
    vespaskills trigger --id sa-03
    vespaskills trigger --trials 3
"""

import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from vespaskills.evals.config import REPO_ROOT
from vespaskills.logger import get_logger

logger = get_logger()

# Trigger evals are Claude-only (requires stream-json event parsing)
CLAUDE_CLI = os.environ.get("CLAUDE_CLI", "claude")
CLAUDE_MODEL = os.environ.get("EVAL_MODEL", "")

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
    """Parse stream-json output to find which skills were invoked."""
    triggered = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        if evt.get("type") != "assistant":
            if evt.get("type") == "user":
                msg = evt.get("message", {})
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, str) and "launching skill:" in content.lower():
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

                if tool_name == "Skill":
                    skill_id = tool_input.get("skill", "")
                    if skill_id:
                        triggered.append(skill_id.lower())
                elif tool_name == "Read":
                    file_path = tool_input.get("file_path", "")
                    if "SKILL.md" in file_path:
                        triggered.append(file_path.lower())

    return triggered


def check_skill_triggered(triggered_skills: list[str], skill_name: str) -> tuple[bool, list[str]]:
    """Check if any triggered skills match the target skill."""
    patterns = SKILL_TRIGGER_PATTERNS.get(skill_name, [skill_name.lower()])
    matched = []

    for triggered in triggered_skills:
        for pattern in patterns:
            if pattern in triggered:
                matched.append(triggered)
                break

    return len(matched) > 0, matched


def run_trigger_test(prompt: str, skill_name: str, timeout: int = 60) -> dict:
    """Run Claude with the plugin installed and detect skill triggering."""
    cmd = [
        CLAUDE_CLI,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "3",
        "--plugin-dir",
        str(REPO_ROOT),
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


def run(args):
    """Run trigger eval command with parsed args."""
    cases = load_trigger_evals(args.csv, args.skill, args.id)
    if not cases:
        logger.error("No test cases found.")
        sys.exit(1)

    logger.info(f"Running {len(cases)} trigger evals ({args.trials} trial(s) each)")
    logger.info(f"Model: {CLAUDE_MODEL or '(default)'}")

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
        for _trial in range(args.trials):
            r = run_trigger_test(prompt, skill, timeout=args.timeout)
            trial_results.append(r)

        trigger_count = sum(1 for r in trial_results if r["triggered"])
        triggered = trigger_count > args.trials / 2

        all_triggered = []
        for r in trial_results:
            all_triggered.extend(r["triggered_skills"])

        if should:
            passed = triggered
        else:
            passed = not triggered

        trigger_str = f"triggered={trigger_count}/{args.trials}"
        expected_str = "should_trigger" if should else "should_NOT_trigger"
        skills_str = f" skills={list(set(all_triggered))}" if all_triggered else ""

        if passed:
            logger.success(f"  [PASS] {case_id} ({category}, {expected_str}): {trigger_str}{skills_str}")
        else:
            logger.error(f"  [FAIL] {case_id} ({category}, {expected_str}): {trigger_str}{skills_str}")
            logger.info(f"         prompt: {prompt[:80]}...")

        results.append(
            {
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
            }
        )

        if passed:
            correct += 1
        total += 1

    logger.info("=" * 60)
    logger.info(f"Results: {correct}/{total} passed ({correct / total:.0%})")

    by_category = {}
    for r in results:
        cat = "should_trigger" if r["should_trigger"] else "should_NOT_trigger"
        by_category.setdefault(cat, {"passed": 0, "total": 0})
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1

    for cat, stats in by_category.items():
        logger.info(f"  {cat}: {stats['passed']}/{stats['total']}" f" ({stats['passed'] / stats['total']:.0%})")

    workspace = REPO_ROOT / f"{cases[0]['skill']}-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    out_path = workspace / "trigger_eval_results.json"
    with open(out_path, "w") as f:
        json.dump(
            {"results": results, "summary": {"correct": correct, "total": total}},
            f,
            indent=2,
        )
    logger.success(f"Saved to: {out_path}")
