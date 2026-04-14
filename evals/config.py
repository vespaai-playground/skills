"""Configuration for skill evaluations."""

from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).parent.parent
EVALS_DIR = Path(__file__).parent
EVALS_JSON = EVALS_DIR / "evals.json"
