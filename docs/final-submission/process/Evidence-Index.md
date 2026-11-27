# EvoAgent Repository and Evaluation Evidence

Repository: [Theo-sssssss/CS5351-Project](https://github.com/Theo-sssssss/CS5351-Project).

Remote Git refs and history were read over the local machine's existing SSH authentication on 23 November 2026. No remote changes were made.

## Observed branch heads

| Branch | Commit | Meaning |
| --- | --- | --- |
| `main` | `faf93a111f24bff749a8dc1c26c9aa56bddf2b88` | V5 source upload |
| `codex/evoagent-final-delivery` | `b9a63e3097635cc5d6f6bad14b82732da43dba02` | Previous delivery baseline at `src/final/EvoAgent` |

The team originally selected [this delivery baseline](https://github.com/Theo-sssssss/CS5351-Project/tree/codex/evoagent-final-delivery/src/final/EvoAgent). V5 on `main` is retained as an incremental version reference. The user-supplied 27 November refresh supersedes the local delivery baseline. The current archive, 99-file inventory and 89-test regression are identified in `../evidence/release/current-delivery-update.json` and `../evidence/release/latest-source-test-run.json`; its source is recorded at commit `e48ee634b7f609a89f761adc8b7a516cb8fcba31` on `main`.

## Increment references

| Increment | Commit date in GMT+8 | Commit | Source location |
| --- | --- | --- | --- |
| V1 core | 13 September 2026 | [5f88441](https://github.com/Theo-sssssss/CS5351-Project/commit/5f884417baa71975b898eeef8a469d126815b829) | `src/sprint1/week1/EvoAgent_v1` |
| V1 source restoration | 22 September 2026 | [258b304](https://github.com/Theo-sssssss/CS5351-Project/commit/258b304f041af6457af73f247838c84aef9e013d) | Same V1 source path |
| V2 | 18 October 2026 | [f231554](https://github.com/Theo-sssssss/CS5351-Project/commit/f2315543fd577c573d1e629d9e39750107047a40) | `src/sprint2/week1/EvoAgent_v2` |
| V3 | 7 November 2026 | [aefe1f7](https://github.com/Theo-sssssss/CS5351-Project/commit/aefe1f741cebf4e840b76726c84be5668a476c1d) | `src/sprint3/week1/EvoAgent_v3` |
| V4 restored snapshot | 21 November 2026 | [7a866fa](https://github.com/Theo-sssssss/CS5351-Project/commit/7a866faddaca3d715b987a1325bf7f2a7772ca5d) | `src/sprint4/week1/EvoAgent_v4` |
| Final-delivery snapshot | 21 November 2026 | [b9a63e3](https://github.com/Theo-sssssss/CS5351-Project/commit/b9a63e3097635cc5d6f6bad14b82732da43dba02) | `src/final/EvoAgent` on the delivery branch |
| V5 restored snapshot | 23 November 2026 | [faf93a1](https://github.com/Theo-sssssss/CS5351-Project/commit/faf93a111f24bff749a8dc1c26c9aa56bddf2b88) | `src/sprint5/week1/EvoAgent_v5` |

## Scope and evaluation references

- [V4 scope at the inspected commit](https://github.com/Theo-sssssss/CS5351-Project/blob/7a866faddaca3d715b987a1325bf7f2a7772ca5d/src/sprint4/week1/EvoAgent_v4/VERSION_SCOPE.md): adaptive context, scoped memory, and declarative Skills; restored source also includes later infrastructure.
- [V5 scope at the inspected commit](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/src/sprint5/week1/EvoAgent_v5/VERSION_SCOPE.md): controlled Skill evolution and maintenance checks.
- [V5 evaluation results](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/src/sprint5/week1/EvoAgent_v5/EVALUATION_RESULTS.md): offline fixture results, negative Skill comparison, and blocked production activation.
- [Final-delivery README](https://github.com/Theo-sssssss/CS5351-Project/blob/b9a63e3097635cc5d6f6bad14b82732da43dba02/src/final/EvoAgent/README.md): batch review, budget recovery, report confirmation, and version workbench.

The supplied handoff archive provides `scrum-records/evidence/*-tests.txt`, `scrum-records/evidence/test-runs.json`, `delivery/Release-Tests.txt`, and `delivery/evaluation/README.md`. Their logged regressions and live pilot outcomes are used in the Sprint records with their original scope and dates. Those archived logs retain their original scope. A separate 27 November run of the current extracted source passed 89 tests; the new log is retained alongside the historical records.

The team supplied the Sprint calendar, six-member roster, and the milestone estimates 216, 186, 132, 72, 30, and 0 hours. The development period is Week 2 through Week 12; the earlier Week 11 endpoint is superseded. Scheduled meeting images supplement the calendar; they do not identify ceremony decisions or individual attendance.

## Team-specified ceremony dates

| Sprint | Planning | Review | Retrospective |
| --- | --- | --- | --- |
| 1 | 7 September 2026 | 2 October 2026 | 2 October 2026 |
| 2 | 12 October 2026 | 6 November 2026 | 6 November 2026 |
| 3 | 9 November 2026 | 27 November 2026 | 27 November 2026 |

Sprint 3 explicitly uses 27 November, superseding the closing-week calculation of 4 December. Its formal period still ends on 30 November. The updated V5 and Sprint 3 records incorporate the team-confirmed completion account dated to the specified 27 November checkpoint. The V3 upload on 7 November occurred after the Sprint 2 Review on 6 November and is treated as Sprint-end follow-up rather than evidence of that Review's demonstration.

## Current-source offline rerun — 27 November 2026

A separate execution from the refreshed 99-file source archive reproduced the controlled fixture metrics: full-workflow aggregate precision/recall/F1 100.00% / 82.50% / 90.41%; held-out precision/recall/F1 100.00% / 62.50% / 76.92%. The evolved Skill gave zero matched holdout gain. The separate 130-case prompt replay also reproduced its metrics and production activation block. These no-LLM results are in `../evidence/evaluation/current-source-20261127/`. The historical increment records and single real-PR pilot remain attributed to their original inputs.

## Current uploaded-source identity

The verified refreshed source is [e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5). The report PDF and LaTeX source are intentionally withheld from this upload. Historical increment links above retain their historical scope.
