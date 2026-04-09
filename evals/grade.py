#!/usr/bin/env python3
# ruff: noqa: T201
"""
Grade eval outputs against assertions.

Supports two grader types:
- Deterministic: file_exists, content_contains, content_matches (regex)
- LLM rubric: sends outputs to Claude for structured evaluation

Usage:
    # Grade all evals in an iteration
    python evals/grade.py --iteration 1

    # Grade a specific eval
    python evals/grade.py --iteration 1 --eval basic-text-search

    # Grade with LLM rubric (requires ANTHROPIC_API_KEY)
    python evals/grade.py --iteration 1 --llm-rubric
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

from config import EVALS_JSON, REPO_ROOT


def load_evals(evals_path: Path) -> dict:
    with open(evals_path) as f:
        return json.load(f)


def find_workspace(skill_name: str, iteration: int) -> Path:
    ws = REPO_ROOT / f"{skill_name}-workspace" / f"iteration-{iteration}"
    if not ws.exists():
        print(f"Error: workspace not found: {ws}")
        sys.exit(1)
    return ws


def check_file_exists(outputs_dir: Path, pattern: str) -> tuple[bool, str]:
    """Check if a file matching the pattern exists in outputs."""
    matches = list(outputs_dir.rglob(pattern))
    if matches:
        return True, f"Found: {', '.join(str(m.relative_to(outputs_dir)) for m in matches)}"
    return False, f"No file matching '{pattern}' found in outputs"


def check_content_contains(outputs_dir: Path, pattern: str, path_glob: str) -> tuple[bool, str]:
    """Check if any file matching path_glob contains the pattern string."""
    files = list(outputs_dir.rglob(path_glob))
    if not files:
        return False, f"No file matching '{path_glob}' found"
    for f in files:
        content = f.read_text(errors="replace")
        if pattern in content:
            # Find the line containing the match for evidence
            for line in content.splitlines():
                if pattern in line:
                    return True, f"Found in {f.name}: {line.strip()[:120]}"
    return False, f"Pattern '{pattern}' not found in {[f.name for f in files]}"


def check_content_matches(outputs_dir: Path, pattern: str, path_glob: str) -> tuple[bool, str]:
    """Check if any file matching path_glob contains text matching the regex."""
    files = list(outputs_dir.rglob(path_glob))
    if not files:
        return False, f"No file matching '{path_glob}' found"
    regex = re.compile(pattern)
    for f in files:
        content = f.read_text(errors="replace")
        match = regex.search(content)
        if match:
            return True, f"Matched in {f.name}: {match.group()[:120]}"
    return False, f"Regex '{pattern}' not matched in {[f.name for f in files]}"


def run_deterministic_assertions(outputs_dir: Path, assertions: list[dict]) -> list[dict]:
    """Run deterministic assertions against output files."""
    results = []
    for assertion in assertions:
        a_type = assertion.get("type", "")
        text = assertion.get("text", f"{a_type}: {assertion.get('pattern', assertion.get('path', ''))}")

        if a_type == "file_exists":
            passed, evidence = check_file_exists(outputs_dir, assertion["path"])
        elif a_type == "content_contains":
            passed, evidence = check_content_contains(
                outputs_dir, assertion["pattern"], assertion.get("path", "*")
            )
        elif a_type == "content_matches":
            passed, evidence = check_content_matches(
                outputs_dir, assertion["pattern"], assertion.get("path", "*")
            )
        else:
            passed, evidence = False, f"Unknown assertion type: {a_type}"

        results.append({"text": text, "passed": passed, "evidence": evidence})
    return results


def run_llm_rubric(outputs_dir: Path, rubric: str, expected_output: str) -> list[dict]:
    """Use Claude to grade outputs against a rubric. Requires anthropic SDK."""
    try:
        import anthropic
    except ImportError:
        return [{"text": "LLM rubric", "passed": False, "evidence": "anthropic SDK not installed (pip install anthropic)"}]

    # Collect all output file contents
    file_contents = []
    for f in sorted(outputs_dir.rglob("*")):
        if f.is_file() and f.suffix in (".sd", ".xml", ".py", ".java", ".json", ".yaml", ".yml", ".txt", ".md", ".cfg"):
            content = f.read_text(errors="replace")
            file_contents.append(f"--- {f.relative_to(outputs_dir)} ---\n{content}")

    if not file_contents:
        return [{"text": "LLM rubric", "passed": False, "evidence": "No output files to grade"}]

    outputs_text = "\n\n".join(file_contents)

    grading_prompt = f"""You are grading the output of an AI coding agent that was asked to create Vespa schema files.

<expected_output>
{expected_output}
</expected_output>

<rubric>
{rubric}
</rubric>

<actual_output>
{outputs_text}
</actual_output>

Evaluate the output against the rubric. For each distinct criterion in the rubric, produce a grading result.

Respond with a JSON array where each element has:
- "text": the criterion being checked (short description)
- "passed": true or false
- "evidence": specific quote or observation from the output supporting your judgment

Be strict: require concrete evidence for a PASS. If something is ambiguous or partially done, mark it as FAIL with explanation.

Respond ONLY with the JSON array, no other text."""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": grading_prompt}],
    )

    try:
        text = response.content[0].text.strip()
        # Handle potential markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError) as e:
        return [{"text": "LLM rubric parsing", "passed": False, "evidence": f"Failed to parse LLM response: {e}"}]


def grade_eval(eval_dir: Path, eval_def: dict, use_llm: bool = False) -> dict:
    """Grade a single eval's with_skill and without_skill outputs."""
    results = {}
    for run_type in ("with_skill", "without_skill"):
        run_dir = eval_dir / run_type
        outputs_dir = run_dir / "outputs"
        if not outputs_dir.exists():
            continue

        assertion_results = []

        # Run deterministic assertions if any
        assertions = eval_def.get("assertions", [])
        if assertions:
            assertion_results.extend(run_deterministic_assertions(outputs_dir, assertions))

        # Run LLM rubric if requested and defined
        if use_llm and eval_def.get("llm_rubric"):
            llm_results = run_llm_rubric(
                outputs_dir,
                eval_def["llm_rubric"],
                eval_def.get("expected_output", ""),
            )
            assertion_results.extend(llm_results)
        elif use_llm and not eval_def.get("llm_rubric"):
            # Use expected_output as a basic rubric
            llm_results = run_llm_rubric(
                outputs_dir,
                f"Does the output match this expectation: {eval_def.get('expected_output', '')}",
                eval_def.get("expected_output", ""),
            )
            assertion_results.extend(llm_results)

        # Compute summary
        total = len(assertion_results)
        passed = sum(1 for r in assertion_results if r["passed"])
        grading = {
            "assertion_results": assertion_results,
            "summary": {
                "passed": passed,
                "failed": total - passed,
                "total": total,
                "pass_rate": passed / total if total > 0 else 0,
            },
        }

        # Save grading.json
        with open(run_dir / "grading.json", "w") as f:
            json.dump(grading, f, indent=2)

        results[run_type] = grading
        print(f"    [{run_type}] {passed}/{total} passed ({grading['summary']['pass_rate']:.0%})")

    return results


def main():
    parser = argparse.ArgumentParser(description="Grade eval outputs")
    parser.add_argument("--iteration", type=int, required=True, help="Iteration number")
    parser.add_argument("--eval", type=str, help="Grade specific eval by name")
    parser.add_argument("--llm-rubric", action="store_true", help="Use LLM-based rubric grading")
    parser.add_argument("--evals-json", type=Path, default=EVALS_JSON)
    args = parser.parse_args()

    evals_data = load_evals(args.evals_json)
    skill_name = evals_data["skill_name"]
    iter_dir = find_workspace(skill_name, args.iteration)

    eval_defs = {e["name"]: e for e in evals_data["evals"]}

    for eval_dir in sorted(iter_dir.iterdir()):
        if not eval_dir.is_dir() or not eval_dir.name.startswith("eval-"):
            continue
        eval_name = eval_dir.name.removeprefix("eval-")
        if args.eval and eval_name != args.eval:
            continue
        if eval_name not in eval_defs:
            print(f"  [{eval_name}] Skipping (not in evals.json)")
            continue

        print(f"  [{eval_name}]")
        grade_eval(eval_dir, eval_defs[eval_name], use_llm=args.llm_rubric)
        print()

    print(f"Done. Grading saved to {iter_dir}/eval-*/{{with,without}}_skill/grading.json")
    print(f"\nNext: python evals/aggregate.py --iteration {args.iteration}")


if __name__ == "__main__":
    main()
