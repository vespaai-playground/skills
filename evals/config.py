"""Configuration for skill evaluations."""

import os
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).parent.parent
EVALS_DIR = Path(__file__).parent
EVALS_JSON = EVALS_DIR / "evals.json"

# Claude CLI settings
CLAUDE_CLI = os.environ.get("CLAUDE_CLI", "claude")
CLAUDE_MODEL = os.environ.get("EVAL_MODEL", "")  # empty = default
CLAUDE_TIMEOUT = int(os.environ.get("EVAL_TIMEOUT", "120"))  # seconds

# Eval settings
MAX_TURNS = int(os.environ.get("EVAL_MAX_TURNS", "20"))
TRIALS_PER_TASK = int(os.environ.get("EVAL_TRIALS", "1"))
