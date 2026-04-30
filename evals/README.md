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

## Adding evals for a skill

Each eval file targets exactly one skill. Use a separate file per skill — the runner reads the file via `--evals-json`, so files don't collide.

### 1. Create the file

`data/evals_<skill-name>.json`:

```json
{
  "skill_name": "<skill-folder-name>",
  "skill_path": "<skill-folder-name>",
  "evals": [
    {
      "id": 1,
      "name": "kebab-case-eval-name",
      "prompt": "Task description. Tell the agent EXPLICITLY to save files to disk (e.g. 'Create a file named foo.xml in the current directory') — Haiku will otherwise print code in chat instead of writing it.",
      "expected_output": "What success looks like (free text — for context only, not graded).",
      "files": ["data/fixtures/<eval-name>/<file>"],
      "assertions": [
        {"type": "file_exists",      "path": "<glob>",   "text": "..."},
        {"type": "content_contains", "path": "<glob>", "pattern": "<substring>", "text": "..."},
        {"type": "content_matches",  "path": "<glob>", "pattern": "<regex>",     "text": "..."}
      ],
      "llm_rubric": "Optional. Detailed criteria for --llm-rubric grading (Sonnet judges)."
    }
  ]
}
```

`path` globs are matched with `rglob` against the agent's output dir, so they find files at any depth. Fixture files listed in `files` are copied into the output dir before the agent runs.

### 2. Aim for diversity across 3+ evals

Cover different shapes so the suite tests breadth, not just one workflow:

- **Greenfield scaffolding** — agent writes multiple files from a spec.
- **Diagnose-and-fix** — provide a fixture with planted bugs; agent identifies and patches them. Plant only bugs that are actually documented as wrong (see step 4).
- **Architecture / non-default features** — exercises less common parts of the skill (e.g. multi-cluster, mixed document modes).

### 3. Run and iterate

```bash
uv run vespaskills eval --evals-json data/evals_<skill>.json --model haiku
uv run vespaskills grade --iteration <N> --evals-json data/evals_<skill>.json
uv run vespaskills aggregate --iteration <N> --evals-json data/evals_<skill>.json
```

Outputs land in `<skill>-workspace/iteration-<N>/`. Inspect the failed assertions and the actual file contents — distinguish *the agent got it wrong* (real signal) from *the assertion is wrong* (fix the eval).

### 4. Verify every assertion against authoritative Vespa sources

Before considering the eval done, cross-check each technical claim in prompts, expected_output, assertions, and rubric against (in priority order):

1. The RNC schema at `vespa/config-model/src/main/resources/schema/*.rnc` — this is what Vespa actually validates against.
2. The Java validation/builder code under `vespa/config-model/src/main/java/`.
3. The official docs Markdown at `documentation/en/` (or [docs.vespa.ai](https://docs.vespa.ai) if the documentation repo isn't cloned locally).
4. Sample apps at `vespa/sample-apps/` for real-world patterns.

The local `SKILL.md` is **not** authoritative — it may overstate or simplify rules. If the SKILL.md and the Vespa source disagree, the source wins (and the SKILL.md needs a fix).

### 5. Common assertion pitfalls

- **Attribute-order brittleness**: regexes like `<document\s+type="X"\s+mode="Y"` fail when the agent writes attributes in the other order. Use lookaheads: `<document\b(?=[^>]*\btype="X")(?=[^>]*\bmode="Y")`.
- **Substring matches that pass vacuously**: e.g. `hugging-face-embedder` as a substring also matches the fully-qualified Java config namespace, defeating the intent. Use a tighter regex like `type="hugging-face-embedder"`.
- **Single-fix assertions for multi-fix bugs**: if the eval prompt accepts two valid fixes, the deterministic assertion must accept both (use alternation, e.g. `<redundancy>1</redundancy>|distribution-key="1"`) — otherwise the LLM rubric and the assertions disagree.
- **Stale syntax**: e.g. `<redundancy>` is being superseded by `<min-redundancy>`. Match both with `<(min-)?redundancy>`.
- **Fixture-vs-fix file collision**: in diagnose-and-fix evals, the fixture file is copied into the output dir; if the agent writes to a different filename, the unmodified fixture still matches the assertion's glob. Always tell the agent to overwrite the fixture filename in place.

### 6. Improve the SKILL.md when the eval reveals a gap

If `with_skill` fails an assertion that the agent would have passed given the right inline guidance, add a minimal example to `SKILL.md` and re-run with `--skip-baseline` to confirm. Keep additions under ~10 lines per change.
