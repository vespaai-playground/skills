# Skill Evaluations

Measure whether Vespa skills improve Claude's output quality on realistic tasks.

## Two Eval Types

**Quality evals** (`run_evals.py`) — Do skills produce better outputs?
- Injects skill content directly into the prompt (controlled comparison)
- Runs each task with and without the skill, compares outputs
- Graded with deterministic checks + LLM rubrics

**Trigger evals** (`run_trigger_evals.py`) — Do skills activate on the right prompts?
- Uses `--plugin-dir` so Claude discovers skills naturally
- Parses stream-json events to detect which skills were invoked
- Tests both should-trigger and should-NOT-trigger cases

## Quick Start

```bash
# Quality evals: run all for schema-authoring
uv run python evals/run_evals.py

# Quality evals: run a single eval
uv run python evals/run_evals.py --eval basic-text-search

# Grade outputs (after reviewing and adding assertions to evals.json)
uv run python evals/grade.py --iteration 1

# Grade with LLM rubric (needs ANTHROPIC_API_KEY)
uv run python evals/grade.py --iteration 1 --llm-rubric

# Aggregate results into benchmark.json
uv run python evals/aggregate.py --iteration 1

# Trigger evals: test skill invocation
uv run python evals/run_trigger_evals.py

# Trigger evals: single test
uv run python evals/run_trigger_evals.py --id sa-03

# Trigger evals: multiple trials for reliability
uv run python evals/run_trigger_evals.py --trials 3
```

## Workflow

Following the [skill-creator eval methodology](https://github.com/anthropics/skills/tree/main/skills/skill-creator):

1. **Write prompts** in `evals/evals.json` (no assertions yet)
2. **Run evals** with `run_evals.py` — launches Claude with and without the skill
3. **Review outputs** manually in `{skill}-workspace/iteration-N/eval-*/`
4. **Draft assertions** based on what you observe, add to `evals.json`
5. **Grade** with `grade.py` (deterministic checks + optional LLM rubric)
6. **Aggregate** with `aggregate.py` to produce `benchmark.json`
7. **Iterate** on the skill, rerun into `iteration-N+1/`

## Directory Structure

```
evals/
├── evals.json              # Quality eval test cases (prompts + assertions)
├── trigger_evals.csv       # Trigger eval test cases (should/should-not trigger)
├── config.py               # Settings (model, timeout, paths)
├── run_evals.py            # Quality eval runner
├── run_trigger_evals.py    # Trigger eval runner
├── grade.py                # Graders: deterministic + LLM rubric
├── aggregate.py            # Benchmark aggregation
└── README.md

schema-authoring-workspace/     # Created by runners (gitignored)
└── iteration-1/
    ├── eval-basic-text-search/
    │   ├── eval_metadata.json
    │   ├── with_skill/
    │   │   ├── outputs/        # Files Claude produced
    │   │   ├── timing.json
    │   │   ├── transcript.json
    │   │   └── grading.json    # After running grade.py
    │   └── without_skill/
    │       └── ...
    ├── run_summary.json
    └── benchmark.json          # After running aggregate.py
```

## Assertion Types

Add assertions to `evals.json` after reviewing first outputs:

```json
{
  "assertions": [
    {"type": "file_exists", "path": "*.sd", "text": "Schema file exists"},
    {"type": "content_contains", "path": "*.sd", "pattern": "schema product", "text": "Correct schema name"},
    {"type": "content_matches", "path": "*.sd", "pattern": "tensor<float>\\(x\\[768\\]\\)", "text": "768-dim tensor"}
  ]
}
```

| Type | Fields | Checks |
|------|--------|--------|
| `file_exists` | `path` (glob) | File matching pattern exists |
| `content_contains` | `path`, `pattern` | File contains exact string |
| `content_matches` | `path`, `pattern` | File matches regex |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EVAL_MODEL` | (CLI default) | Claude model to use |
| `EVAL_TIMEOUT` | `120` | Timeout per run in seconds |
| `EVAL_MAX_TURNS` | `20` | Max agent turns per run |
| `EVAL_TRIALS` | `1` | Trials per task (for pass@k) |
| `CLAUDE_CLI` | `claude` | Path to Claude CLI |

## Plugin Setup

The `skills/` directory contains symlinks to the skill directories, enabling
Claude Code plugin discovery via `--plugin-dir .`. This is used by the trigger
eval runner.

If the `vespa-support` plugin (from `vespa-claude`) is installed at user scope
and interferes with trigger evals, disable it for this workspace:

```json
// .claude/settings.local.json
{
  "enabledPlugins": {
    "vespa-support@vespa-claude": false
  }
}
```

## Writing Good Trigger Eval Prompts

Claude only consults skills for tasks it can't easily handle on its own.
Simple questions (e.g. "how do I add BM25 ranking?") won't trigger skills
because Claude answers from training data. Trigger eval prompts must be
**substantive, multi-step tasks** where consulting the skill adds real value.

**Won't trigger** (too simple):
```
how do I add BM25 ranking to my Vespa schema?
```

**Will trigger** (actionable task):
```
Create a vespa schema for a recipe search app — it needs fields for title,
ingredients as an array, cooking_time integer, a 512-dim embedding for semantic
search with HNSW, and a hybrid rank profile. Write it to schemas/recipe.sd
```

## Adding Evals for Other Skills

1. Add test cases to `evals.json` (or create a new one) with `skill_name` and `skill_path`
2. Run: `uv run python evals/run_evals.py --evals-json path/to/evals.json`
3. Same grade/aggregate workflow applies
4. For trigger evals, add rows to `trigger_evals.csv` and update `SKILL_TRIGGER_PATTERNS` in `run_trigger_evals.py`
