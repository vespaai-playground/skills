"""
Provider abstraction for running coding agents in eval mode.

Currently supports Claude Code CLI. The Provider base class can be
extended with additional providers (e.g. OpenCode) in the future.

Usage:
    provider = get_provider()
    result = provider.run_prompt("Create a schema...", work_dir=Path("/tmp/test"))

Configuration via environment variables:
    EVAL_MODEL     - Model to use (e.g. "claude-sonnet-4-20250514")
    EVAL_TIMEOUT   - Timeout in seconds (default: 120)
    EVAL_MAX_TURNS - Max agent turns (default: 20)
    CLAUDE_CLI     - Path to claude binary (default: "claude")
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    """Result from a provider run."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    output_files: list[str]


class Provider:
    """Base class for coding agent providers. Extend this to add new providers."""

    name: str = "base"

    def __init__(self, model: str = "", timeout: int = 120):
        self.model = model
        self.timeout = timeout

    def run_prompt(
        self,
        prompt: str,
        work_dir: Path,
        skill_content: str | None = None,
        timeout: int | None = None,
    ) -> RunResult:
        """
        Run a prompt through the coding agent.

        Args:
            prompt: The task prompt
            work_dir: Working directory for the agent
            skill_content: Optional skill SKILL.md content to inject into the prompt
            timeout: Override default timeout (seconds)
        """
        effective_timeout = timeout or self.timeout

        if skill_content:
            prompt = (
                f"You have access to the following skill for reference:\n\n"
                f"<skill>\n{skill_content}\n</skill>\n\n"
                f"Use the skill above to help with this task:\n\n{prompt}"
            )

        return self._run(prompt, work_dir, effective_timeout)

    def _run(self, prompt: str, work_dir: Path, timeout: int) -> RunResult:
        raise NotImplementedError

    def extract_usage(self, stdout: str) -> dict:
        """Extract token usage / cost info from provider output."""
        return {}

    def _collect_output_files(self, work_dir: Path) -> list[str]:
        """Collect files created in work_dir."""
        files = []
        for f in work_dir.rglob("*"):
            if f.is_file() and not f.is_symlink() and f.name not in (".DS_Store",):
                files.append(str(f.relative_to(work_dir)))
        return files


class ClaudeProvider(Provider):
    """Claude Code CLI provider."""

    name = "claude"

    def __init__(self, model: str = "", timeout: int = 120, max_turns: int = 20):
        super().__init__(model, timeout)
        self.cli = os.environ.get("CLAUDE_CLI", "claude")
        self.max_turns = max_turns

    def _run(self, prompt: str, work_dir: Path, timeout: int) -> RunResult:
        cmd = [
            self.cli,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--max-turns",
            str(self.max_turns),
            "--dangerously-skip-permissions",
        ]
        if self.model:
            cmd.extend(["--model", self.model])

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
            return RunResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                output_files=self._collect_output_files(work_dir),
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            return RunResult(
                exit_code=124,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=duration_ms,
                output_files=[],
            )

    def extract_usage(self, stdout: str) -> dict:
        try:
            data = json.loads(stdout)
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


def get_provider(model: str | None = None, timeout: int | None = None) -> ClaudeProvider:
    """
    Create a Claude provider instance.

    Args:
        model: Model override. Default: EVAL_MODEL env var.
        timeout: Timeout in seconds. Default: EVAL_TIMEOUT env var or 120.
    """
    return ClaudeProvider(
        model=model or os.environ.get("EVAL_MODEL", ""),
        timeout=timeout or int(os.environ.get("EVAL_TIMEOUT", "120")),
        max_turns=int(os.environ.get("EVAL_MAX_TURNS", "20")),
    )
