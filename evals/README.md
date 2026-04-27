# Skill Evaluations

The `vespaskills` CLI runs a coding agent against a fixed set of tasks twice — once with the skill loaded and once without — and aggregates the results into a benchmark report. The pipeline is `eval` (or `eval-discovery`) → `grade` → `aggregate`.

Eval definitions live in [`data/evals.json`](../data/evals.json). Outputs land in `{skill}-workspace/iteration-N/` (or `{skill}-workspace-discovery/iteration-N/` for discovery mode).

## Commands

### `eval` — injection mode

```bash
uv run vespaskills eval --model haiku
```

Runs every eval twice per skill: once with `SKILL.md` prepended into the prompt (`with_skill`) and once without (`without_skill`). This isolates the *content* of the skill from any discovery/triggering effects — if the model has the skill text in front of it, does it produce better output?

Useful flags: `--eval <name>` to run a single eval, `--iteration N` to pin the iteration number, `--skip-baseline` / `--skip-with-skill` to run only one arm.

### `eval-discovery` — discovery mode

```bash
uv run vespaskills eval-discovery
```

Same prompts, but the skill is loaded as a plugin via `--plugin-dir` instead of being injected. Claude decides for itself whether to invoke the skill, so this measures realistic end-user token cost and exposes how good the skill's trigger description is. Each run records `invoked: bool` indicating whether the target skill actually fired.

Outputs go to `{skill}-workspace-discovery/iteration-N/`.

### `aggregate` — build the benchmark report

```bash
uv run vespaskills aggregate --iteration 102
```

Reads grading and timing JSON from a finished iteration, computes per-eval and overall means, and writes `benchmark.json` plus a human-readable `benchmark.md` next to it. Pass `--workspace-suffix -discovery` to aggregate a discovery-mode iteration.

Example output:

```markdown
# Skill Benchmark — schema-authoring (iteration 102)

## Summary (mean per eval)

| Metric | with_skill | without_skill | Δ abs | Δ % |
|---|---:|---:|---:|---:|
| pass rate | 89.2% | 76.1% | +13.1% | — |
| total input tokens | 170,731 | 152,407 | +18,324 | +12.0% |
| output tokens | 4,080 | 3,026 | +1,054 | +34.8% |
| cost usd | $0.0536 | $0.0419 | +$0.0117 | +27.9% |

- Evals: **7**

## Per-eval breakdown

| Eval | pass (with) | pass (without) | invoked | cost (with) | cost (without) |
|---|:---:|:---:|:---:|---:|---:|
| complex-field-types | 10/11 | 10/11 | — | $0.0512 | $0.0281 |
| diagnose-and-fix | 5/5 | 5/5 | — | $0.0532 | $0.0568 |
| extend-existing-schema | 7/8 | 7/8 | — | $0.0658 | $0.0473 |
| fix-subtle-bugs | 4/4 | 2/4 | — | $0.0482 | $0.0317 |
| gotcha-heavy-schema | 10/12 | 9/12 | — | $0.0499 | $0.0504 |
| large-scale-schema-design | 5/8 | 5/8 | — | $0.0492 | $0.0388 |
| parent-child-with-ranking | 9/9 | 6/9 | — | $0.0577 | $0.0399 |
```

## Typical workflow

```bash
uv run vespaskills eval --model haiku        # 1. run the agent (or eval-discovery)
uv run vespaskills grade --iteration 102     # 2. score outputs against assertions
uv run vespaskills aggregate --iteration 102 # 3. build benchmark.json + benchmark.md
```
