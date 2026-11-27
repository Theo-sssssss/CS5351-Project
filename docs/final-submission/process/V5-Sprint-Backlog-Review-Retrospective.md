# Sprint 3 V5 Backlog, Review and Retrospective

Reporting checkpoint: 27 November 2026, as specified by the team. This completion account combines the team's confirmation of allocated work with inspection of the archived V5 source and existing test and evaluation records. V5 was uploaded on 23 November at `faf93a1`. The earlier selected delivery baseline is `b9a63e3`. The current local delivery is the user-supplied 27 November refresh, identified by its 99-file manifest and a separate 89-test passing regression record.

Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Completed V5 Sprint Backlog

**Goal.** Convert scoped repository feedback into versioned review-skill candidates, evaluate them on fixed partitions, and enforce activation and rollback controls.

Members completed their allocated work and handed their outputs to Jiexuan Shen for integration and centralized GitHub submission. The owners below reflect the team-confirmed allocation. Each member recorded 36 hours across V1–V5; this record adds no task-level hour estimates.

| ID | Owner | Completed scope | Verification and outcome |
| --- | --- | --- | --- |
| V5-01 | Siye Tu | Candidate Skill generation from scoped feedback, with artifact identity and source evidence. | `SkillEvolutionEngine.auto_propose` and `build_candidate_artifact` implement the path. `test_auto_evolution_writes_learned_guidance_into_skill_md` checks learned guidance and resolved feedback. Completed. |
| V5-02 | Jianyu Zhou | Fixed evaluation partitions and comparison of static, evolved and random-feedback Skills. | Repository-disjoint 60/20/20 split for 100 synthetic cases. Full workflow and evolved workflow aggregate F1 were both 90.41%; the matched holdout showed no Skill gain. Completed with the negative result retained. |
| V5-03 | Xinyu Zhang | Candidate validation, tenant boundaries, activation and rollback controls. | `test_active_agent_skills_are_tenant_isolated_and_override_disk` checks isolation; `test_holdout_regression_blocks_activation_without_leaking_case_details` checks rejection. `SkillEvolutionEngine.rollback` provides version restoration, and `test_canary_assignment_and_error_budget_rollback` covers rollout recovery. The prompt replay's production activation was blocked by provenance checks. Completed. |
| V5-04 | Tianyi Jiang | Maintenance procedure, dependency guidance and reproducible archived inputs. | [V5 regression log](../evidence/regression/EvoAgent_v5-tests.txt) records 70 passing tests. The restored snapshot contains the evaluation fixtures. The log also retains database-closure ResourceWarnings. Completed within the recorded regression scope. |
| V5-05 | Jiayu Zhu | Demonstration preparation and user-flow verification. | V5 candidate replay and release eligibility are supported by the evolution tests. The selected final snapshot has a separate [deterministic trace](../evidence/evaluation/demo-trace.json), recording pause at 2/12 batches, resume to 12/12, and report confirmation with result `PASS`. Completed. |
| V5-06 | Jiexuan Shen | Integration, centralized submission, source identity and evidence reconciliation. | [Current release verification](../evidence/release/latest-source-test-run.json) identifies the refreshed source and records 89 passing tests. V5 results and final-runtime evidence remain attributed to their respective snapshots. Completed. |

## 27 November Sprint Review Outcomes

The team confirmed completion of the documented V5 scope. Inspection covered feedback-to-candidate generation, replay outcomes, isolation, activation controls and rollback support. The existing V5 regression record passed all 70 tests. That historical V5 result is retained. A separate final delivery check on 27 November passed 89 tests from the refreshed source ZIP; see `../evidence/release/latest-source-test-run.json`. It does not replace the historical V5 baseline. A separate current-source experimental rerun is documented below.

The 100-case controlled experiment uses simulated reviewers without real model calls. Its aggregate precision, recall and F1 are recorded in [V5 evaluation results](../evidence/evaluation/V5-Evaluation-Results.md). The separate 130-case prompt replay increased validation and holdout F1 from 66.67% to 100%, while the production provenance gate correctly blocked activation. Candidate rejection and activation blocks are expected successful control outcomes under those inputs.

The final-runtime walkthrough used the selected final snapshot's deterministic trace. It verified preserved progress, completion after resume and report revision confirmation. The current delivery source passed 89 regression tests on 27 November. The separate real-model pilot completed one public documentation PR in batched mode; the legacy path exhausted its budget. The pilot provides execution evidence on that input.

**Acceptance decision.** The team accepted the demonstrated prototype scope and archived verification results for V5 and the selected final delivery. The synthetic experiments and single unlabelled PR retain their stated evaluation limits. Presentation rehearsal and official submission remain delivery activities.

## 27 November Sprint Retrospective Outcomes

| Lesson | Evidence considered | Completed response and follow-up |
| --- | --- | --- |
| Release fixtures must travel with the snapshot. | V4 maintenance failures and the repaired V5 regression inputs. | Tianyi Jiang retained setup and fixture guidance. Clean-install rehearsal remains part of final delivery preparation. |
| Record negative results and release decisions explicitly. | No matched holdout Skill gain; prompt replay passed numeric checks and failed production provenance checks. | Jianyu Zhou and Siye Tu reconciled experiment outcomes in the evaluation record. The report preserves dataset provenance and the separate activation outcome. |
| Show incomplete review state and recovery. | Final deterministic trace passed pause, resume and confirmation. | Jiayu Zhu prepared the walkthrough. Rehearse it within the presentation's combined five-minute allowance for slides and demo. |
| Preserve access and regression evidence. | Tenant-isolation and release-control tests; archived V5 and final regression logs. | Xinyu Zhang retained the controls and logs, including the remaining ResourceWarnings as maintenance observations. |
| Centralized uploads need an accompanying allocation record. | Team backlogs, actual-effort workbook and member handoffs. | Jiexuan Shen consolidated the team allocation, source identity and completion account. The user confirmed the biographies and reflections, now included in the report. |

## Source Inspection References

Inspected files in the archived `EvoAgent_v5` snapshot include `VERSION_SCOPE.md`, `EVALUATION_RESULTS.md`, `evoagent/skill_evolution.py`, `tests/test_skill_evolution.py`, `tests/test_advanced.py`, `tests/test_evaluation_experiments.py` and `tests/test_production_features.py`. V5 contains shared infrastructure; its intended increment is controlled Skill evolution. Final batching and confirmation evidence is attributed to the selected final snapshot.

[scope]: https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/src/sprint5/week1/EvoAgent_v5/VERSION_SCOPE.md
[evaluation]: https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/src/sprint5/week1/EvoAgent_v5/EVALUATION_RESULTS.md
[skills]: https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/src/sprint5/week1/EvoAgent_v5/tests/test_skill_evolution.py
[maintenance]: https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/src/sprint5/week1/EvoAgent_v5/scripts/run_maintenance.py

## Current-source offline rerun — 27 November 2026

A separate execution from the refreshed 99-file source archive reproduced the controlled fixture metrics: full-workflow aggregate precision/recall/F1 100.00% / 82.50% / 90.41%; held-out precision/recall/F1 100.00% / 62.50% / 76.92%. The evolved Skill gave zero matched holdout gain. The separate 130-case prompt replay also reproduced its metrics and production activation block. These no-LLM results are in `../evidence/evaluation/current-source-20261127/`. The historical increment records and single real-PR pilot remain attributed to their original inputs.

## Current uploaded-source identity

The verified refreshed source is [e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5). The report PDF and LaTeX source are intentionally withheld from this upload. Historical increment links above retain their historical scope.
