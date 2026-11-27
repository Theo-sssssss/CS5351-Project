# EvoAgent V5 Evaluation Results

## Scope and reproducibility

The V5 automated test suite passed all 70 tests using the project's Python environment. Two offline datasets supplied with the recovered EvoAgent project were used for the experiments: `evaluation_data/pr_diff_100.jsonl` (100 cases) and `evaluation_data/prompt_evolution_130.jsonl` (130 cases). Both identify their provenance as `offline-fixture`. The controlled experiment used repository-disjoint train, validation, and holdout splits of 60, 20, and 20 cases. The prompt evolution replay used 104 validation and 26 holdout cases.

Run from the V5 project directory with dependencies installed:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/run_controlled_experiments.py
python3 scripts/run_prompt_evolution_proof.py --output-dir output/prompt-evolution-proof-new-run
```

The prompt evolution proof requires a fresh output directory for each run because it writes an immutable SQLite run record. Full machine-readable outputs from this run are in `output/controlled-experiments/evaluation.json` and `output/prompt-evolution-proof/prompt-evolution-proof.json`.

## Controlled offline comparison

The experiment ran without an LLM. It measures deterministic rules, simulated reviewer orchestration, and Skill selection gates; arm names do not imply real model calls. Across the 100-case controlled set:

| Arm | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| Single simulated model | 83.33% | 62.50% | 71.43% |
| Single simulated model with scanner | 82.50% | 82.50% | 82.50% |
| Multi-agent without Critic | 82.50% | 82.50% | 82.50% |
| Full agentic workflow | 100.00% | 82.50% | 90.41% |
| Full agentic workflow with evolved Skill | 100.00% | 82.50% | 90.41% |

These overall arm scores are not the same measure as the paired holdout comparisons. On the held-out split, the F1 difference for Critic versus no Critic, multi-agent versus single with scanner, and evolved Skill versus full agentic was **0**. Scanner versus single-model baseline improved holdout F1 by **22.37 percentage points** in this offline setup.

The Skill evolution experiment compared static, evolved, and random-feedback Skills. All three had F1 **54.55%** on the measured split. The validation candidate did not meet the required improvement threshold, and the holdout activation gate remained blocked. This is a negative result for Skill improvement in this controlled experiment.

## Prompt evolution replay

On a separate 130-case offline fixture set, feedback-driven Prompt v2 improved F1 from **66.67% to 100.00%** on validation and from **66.67% to 100.00%** on holdout. The numerical gate passed. However, the production provenance gate failed and production activation was blocked. This demonstrates the replay and gating mechanism on fixtures, not real-world effectiveness.

## Evidence boundary and next evaluation

The available datasets are offline fixtures, and the controlled experiment did not call a real LLM. Accordingly, these results cannot support claims that EvoAgent outperforms external code-review tools or achieves these metrics on real GitHub pull requests. A real-world comparison requires a human-labelled public or historical PR dataset, a specified baseline and model, identical case ordering and budgets across arms, and a saved experimental result. V5's production-readiness validator defaults to at least 300 cases with repository-isolated train, validation, and hidden holdout splits. The 300-case threshold is the tool's own gate, not a separate numerical requirement stated in the course slides.
