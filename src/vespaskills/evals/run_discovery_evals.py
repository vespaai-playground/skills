"""Run skill evaluations in DISCOVERY mode.

Unlike `run_evals.py` (injection mode — prepends SKILL.md into the prompt),
this runner loads the plugin via `--plugin-dir` so Claude decides for itself
whether to invoke the skill. This gives realistic end-user token cost and
exposes trigger-description quality.

Outputs are written to `{skill_name}-workspace-discovery/iteration-N/` and
the directory layout matches `run_evals.py`, so `grade.py` and `aggregate.py`
work unchanged when passed `--workspace-suffix -discovery`.

The `with_skill` arm enables `--plugin-dir`. The `without_skill` arm runs
the same prompt without the plugin as a baseline. Each `timing.json` also
records `invoked: bool` — whether the target skill actually fired on that run.

Usage:
    vespaskills eval-discovery
    vespaskills eval-discovery --eval extend-existing-schema
    vespaskills eval-discovery --skip-baseline
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from vespaskills.evals.config import REPO_ROOT
from vespaskills.evals.run_evals import get_next_iteration, load_evals
from vespaskills.evals.run_trigger_evals import check_skill_triggered, parse_triggered_skills
from vespaskills.logger import get_logger

logger = get_logger()

WORKSPACE_SUFFIX = "-discovery"


def extract_usage_from_stream(stdout: str) -> dict:
    """Parse stream-json lines; pull usage, cost, turns from the final `result` event."""
    out = {}
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "result":
            if isinstance(evt.get("usage"), dict):
                out.update(evt["usage"])
            if "total_cost_usd" in evt:
                out["cost_usd"] = evt["total_cost_usd"]
            if "num_turns" in evt:
                out["num_turns"] = evt["num_turns"]

    input_parts = [
        out.get("input_tokens", 0) or 0,
        out.get("cache_creation_input_tokens", 0) or 0,
        out.get("cache_read_input_tokens", 0) or 0,
    ]
    if any(input_parts):
        out["total_input_tokens"] = sum(input_parts)
    return out


def run_discovery_prompt(
    prompt: str,
    work_dir: Path,
    include_plugin: bool,
    model: str,
    timeout: int,
    max_turns: int,
) -> tuple[subprocess.CompletedProcess | None, int]:
    """Invoke Claude CLI in stream-json mode; return (result, duration_ms)."""
    cli = os.environ.get("CLAUDE_CLI", "claude")
    cmd = [
        cli,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        str(max_turns),
        "--dangerously-skip-permissions",
    ]
    if include_plugin:
        cmd.extend(["--plugin-dir", str(REPO_ROOT)])
    if model:
        cmd.extend(["--model", model])

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
        return result, int((time.time() - start) * 1000)
    except subprocess.TimeoutExpired:
        return None, int((time.time() - start) * 1000)


def run_single_eval(
    eval_def: dict,
    skill_name: str,
    eval_dir: Path,
    run_type: str,
    model: str,
    timeout: int,
    max_turns: int,
) -> dict:
    run_dir = eval_dir / run_type
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Copy fixtures (same convention as run_evals.py)
    for fixture in eval_def.get("files", []):
        src = Path(fixture)
        if not src.is_absolute():
            src = REPO_ROOT / src
        if src.exists():
            shutil.copy2(src, outputs_dir / src.name)

    logger.info(f"    [{run_type}] Running (claude discovery)...")

    include_plugin = run_type == "with_skill"
    result, duration_ms = run_discovery_prompt(
        eval_def["prompt"], outputs_dir, include_plugin, model, timeout, max_turns
    )

    if result is None:
        timing = {
            "provider": "claude",
            "mode": "discovery",
            "model": model or "(default)",
            "duration_ms": duration_ms,
            "exit_code": 124,
            "invoked": False,
            "invoked_skills": [],
        }
        with open(run_dir / "timing.json", "w") as f:
            json.dump(timing, f, indent=2)
        logger.warning(f"    [{run_type}] timeout ({duration_ms}ms)")
        return timing

    # Recover any files Claude wrote outside outputs_dir (e.g. schemas/ at repo root)
    for leaked_dir in ("schemas",):
        leaked_path = REPO_ROOT / leaked_dir
        if leaked_path.exists() and leaked_path.is_dir():
            dest = outputs_dir / leaked_dir
            dest.mkdir(parents=True, exist_ok=True)
            for f in leaked_path.rglob("*"):
                if f.is_file():
                    target = dest / f.relative_to(leaked_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(target))
            shutil.rmtree(leaked_path, ignore_errors=True)

    usage = extract_usage_from_stream(result.stdout)
    triggered_list = parse_triggered_skills(result.stdout)
    invoked, matched = check_skill_triggered(triggered_list, skill_name)

    timing = {
        "provider": "claude",
        "mode": "discovery",
        "model": model or "(default)",
        "duration_ms": duration_ms,
        "exit_code": result.returncode,
        "invoked": invoked if run_type == "with_skill" else False,
        "invoked_skills": matched,
        "all_triggered_skills": triggered_list,
        **usage,
    }

    with open(run_dir / "timing.json", "w") as f:
        json.dump(timing, f, indent=2)

    # Raw stream for debugging; keep a minimal transcript.json for grade.py compatibility.
    with open(run_dir / "stream.jsonl", "w") as f:
        f.write(result.stdout or "")
    with open(run_dir / "transcript.json", "w") as f:
        json.dump(
            {"mode": "discovery", "stream_file": "stream.jsonl", "num_events": len(result.stdout.splitlines())},
            f,
        )
    if result.stderr:
        with open(run_dir / "stderr.txt", "w") as f:
            f.write(result.stderr)

    status = "ok" if result.returncode == 0 else "error"
    marker = " [SKILL INVOKED]" if (run_type == "with_skill" and invoked) else ""
    output_files = [str(p.relative_to(outputs_dir)) for p in outputs_dir.rglob("*") if p.is_file()]
    if result.returncode == 0:
        logger.success(f"    [{run_type}] {status} ({duration_ms}ms, {len(output_files)} files){marker}")
    else:
        logger.warning(f"    [{run_type}] {status} ({duration_ms}ms, {len(output_files)} files){marker}")
    return timing


def run(args):
    """Run discovery-mode eval command with parsed args."""
    evals_data = load_evals(args.evals_json, args.eval)
    skill_name = evals_data["skill_name"]
    skill_path = REPO_ROOT / evals_data["skill_path"]

    if not skill_path.exists():
        logger.error(f"Skill path not found: {skill_path}")
        sys.exit(1)

    workspace = REPO_ROOT / f"{skill_name}-workspace{WORKSPACE_SUFFIX}"
    iteration = args.iteration or get_next_iteration(workspace)
    iter_dir = workspace / f"iteration-{iteration}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    model = args.model or os.environ.get("EVAL_MODEL", "")
    timeout = int(os.environ.get("EVAL_TIMEOUT", "120"))
    max_turns = int(os.environ.get("EVAL_MAX_TURNS", "20"))

    logger.info(f"Skill: {skill_name} (DISCOVERY mode — --plugin-dir)")
    logger.info(f"Model: {model or '(default)'}")
    logger.info(f"Workspace: {iter_dir}")
    logger.info(f"Evals: {len(evals_data['evals'])}")

    all_timings = {}
    for eval_def in evals_data["evals"]:
        eval_name = eval_def["name"]
        eval_dir = iter_dir / f"eval-{eval_name}"
        eval_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "eval_id": eval_def["id"],
            "eval_name": eval_name,
            "mode": "discovery",
            "prompt": eval_def["prompt"],
            "expected_output": eval_def["expected_output"],
            "assertions": eval_def.get("assertions", []),
        }
        with open(eval_dir / "eval_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"  [{eval_name}]")
        timings = {}
        if not args.skip_with_skill:
            timings["with_skill"] = run_single_eval(
                eval_def, skill_name, eval_dir, "with_skill", model, timeout, max_turns
            )
        if not args.skip_baseline:
            timings["without_skill"] = run_single_eval(
                eval_def, skill_name, eval_dir, "without_skill", model, timeout, max_turns
            )
        all_timings[eval_name] = timings

    summary = {
        "skill": skill_name,
        "mode": "discovery",
        "iteration": iteration,
        "model": model or "(default)",
        "eval_count": len(evals_data["evals"]),
        "timings": all_timings,
    }
    with open(iter_dir / "run_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.success(f"Done. Results in: {iter_dir}")
    logger.info("Next steps:")
    logger.info(f"  1. vespaskills grade --iteration {iteration} --workspace-suffix {WORKSPACE_SUFFIX}")
    logger.info(f"  2. vespaskills aggregate --iteration {iteration} --workspace-suffix {WORKSPACE_SUFFIX}")
