# Skill Evaluations

Measure whether Vespa skills improve Claude's output quality on realistic tasks.

## Quick Start

```bash
# Run all evals for schema-authoring (with-skill + baseline)
python evals/run_evals.py

# Run a single eval
python evals/run_evals.py --eval basic-text-search

# After reviewing outputs, add assertions to evals.json, then grade
python evals/grade.py --iteration 1

# Grade with LLM rubric (needs ANTHROPIC_API_KEY)
python evals/grade.py --iteration 1 --llm-rubric

# Aggregate results into benchmark.json
python evals/aggregate.py --iteration 1
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
├── evals.json          # Test cases (prompts + assertions)
├── config.py           # Settings (model, timeout, paths)
├── run_evals.py        # Runner: Claude CLI with/without skill
├── grade.py            # Graders: deterministic + LLM rubric
├── aggregate.py        # Benchmark aggregation
└── README.md

schema-authoring-workspace/     # Created by run_evals.py (gitignored)
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
    {"type": "file_exists", "path": "*.sd"},
    {"type": "content_contains", "path": "*.sd", "pattern": "schema product"},
    {"type": "content_matches", "path": "*.sd", "pattern": "tensor<float>\\(x\\[768\\]\\)"}
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

## Adding Evals for Other Skills

1. Create a new `evals.json` (or add to existing) with `skill_name` and `skill_path` pointing to the skill directory
2. Run: `python evals/run_evals.py --evals-json path/to/evals.json`
3. Same grade/aggregate workflow applies
