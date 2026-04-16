"""Configuration for skill evaluations."""

from pathlib import Path

# Repo root is the working directory (commands are run from repo root)
REPO_ROOT = Path.cwd()

# Data files live in data/ at the repo root
DATA_DIR = REPO_ROOT / "data"
EVALS_JSON = DATA_DIR / "evals.json"
TRIGGER_EVALS_CSV = DATA_DIR / "trigger_evals.csv"
