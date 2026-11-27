# Current Source Offline Evaluation — 27 November 2026

Fresh execution from the current 99-file source ZIP using Python 3.11.5. Both scripts exited successfully. The source archive SHA-256, dataset file hashes, commands, seed (20260819), bootstrap iterations (1000) and durations are recorded in `run-metadata.json`. Dependency versions are in `dependencies.txt`.

## Protocol and scope

Execution mode: `controlled-offline-no-llm`. These runs used deterministic rules and simulated reviewer orchestration, not a real language model. The 100-case fixture has 40 risk cases and 60 clean cases. Its repository-disjoint split is 60 train, 20 validation and 20 holdout. No new real-PR pilot or labelled real-world accuracy study was run.

## Five-arm aggregate comparison: all 100 cases

| Arm | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Single simulated model | 25 | 5 | 15 | 83.33% | 62.50% | 71.43% |
| Single simulated model with scanner | 33 | 7 | 7 | 82.50% | 82.50% | 82.50% |
| Multi-agent without Critic | 33 | 7 | 7 | 82.50% | 82.50% | 82.50% |
| Full agentic workflow | 33 | 0 | 7 | 100.00% | 82.50% | 90.41% |
| Full workflow with evolved Skill | 33 | 0 | 7 | 100.00% | 82.50% | 90.41% |

These figures pool train, validation and holdout. They reproduce the previously reported aggregate metrics on this fixed synthetic dataset. They must not be presented as held-out accuracy.

## Held-out comparison: 20 cases

| Arm | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Single simulated model | 3 | 0 | 5 | 100.00% | 37.50% | 54.55% |
| Single simulated model with scanner | 5 | 0 | 3 | 100.00% | 62.50% | 76.92% |
| Multi-agent without Critic | 5 | 0 | 3 | 100.00% | 62.50% | 76.92% |
| Full agentic workflow | 5 | 0 | 3 | 100.00% | 62.50% | 76.92% |
| Full workflow with evolved Skill | 5 | 0 | 3 | 100.00% | 62.50% | 76.92% |

The evolved Skill adds zero held-out F1 compared with the matched full workflow. Critic versus no Critic and multi-agent versus single model with scanner also have zero held-out F1 difference here. Scanner versus single simulated model has a reported +22.37 percentage-point held-out F1 difference. This is a result for the fixture harness.

## Separate Skill-policy experiment

Static, evolved and random-feedback policies each measured precision 100.00%, recall 37.50% and F1 54.55% on their held-out comparison. The validation candidate was rejected for insufficient F1 gain. These are separate arms from the full-workflow comparison above.

## Separate 130-case prompt replay

| Split | Version | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: |
| validation | baseline | 100.00% | 50.00% | 66.67% |
| validation | candidate | 100.00% | 100.00% | 100.00% |
| holdout | baseline | 100.00% | 50.00% | 66.67% |
| holdout | candidate | 100.00% | 100.00% | 100.00% |

The replay used 104 validation and 26 holdout cases. Its isolated offline record has decision `activated`, while `release_gate.production_activation_allowed` is `false`: numerical checks passed, but production provenance failed. Offline replay activation is not production publication.

## Reproduction

From a fresh extraction of the matching source ZIP with dependencies installed:

```bash
python scripts/run_controlled_experiments.py --seed 20260819 --bootstrap-iterations 1000 --output /path/to/fresh-output/controlled/evaluation.json
python scripts/run_prompt_evolution_proof.py --output-dir /path/to/fresh-output/prompt
```

Use a new prompt output directory because the proof run writes an immutable SQLite record. The temporary database is not distributed as application state. Raw JSON results and console logs are retained beside this summary. No benchmark labels, matching rules, thresholds or source files were edited for this rerun.

## English documentation refresh — 28 November 2026

The final source archive now has translated `README.md` and `RUN-LOCAL.md`. All other 97 distributable files, including implementation, configuration and experiment fixtures, match the measured 27 November archive byte for byte. Raw results and `run-metadata.json` retain the original measured archive identity. The documentation refresh passed a fresh 89-test regression; it does not introduce a new accuracy experiment.
