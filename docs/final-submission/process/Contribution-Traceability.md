# Contribution Traceability

Group 04. Team name: **group**. Documentation updated on 28 November 2026.

The sources below record backlog ownership. A planned owner is evidence of assigned responsibility. Completed work and actual hours require corroboration from commits, reviews, acceptance records or the person's contribution statement. V1 rows carrying only a letter code are left unattributed where the mapping is unclear. The V3 repair packages are listed as assigned scope. Their inclusion here makes no claim that each planned feature shipped.

| Member | V1 named tasks | V2 | V3 | V4 | Team-confirmed V5 and final delivery responsibility |
| --- | --- | --- | --- | --- | --- |
| Tianyi Jiang | PR metadata and diff retrieval (SB-05) | QA and Scrum (SB13--SB15) | Runtime, budgets, and checkpoint recovery (01--03) | Risk ranking and bounded diff context (T01--T03) | V5-04 completed: maintained dependency/setup guidance and packaged evaluation fixtures and source identities. |
| Jianyu Zhou | Runtime artifact handling and baseline model call (SB-03, SB-08) | Review integrity (SB06, SB09, SB12) | Tool contracts and read-only inspection (04--06) | Scoped memory, recall and expiry (T04--T06) | V5-02 completed: fixed evaluation partitions and reconciled comparative metrics, provenance and claim limits. |
| Jiayu Zhu | PR URL validation (SB-04) | Platform integration (SB07--SB08) | UI, API, acceptance tests and demo (16--18) | Adaptive integration and release handoff (T16--T18) | V5-05 completed: prepared the demonstration and verified submission, coverage, resume and report confirmation. |
| Siye Tu | Local HTTP service and dashboard hosting (SB-02) | Model integration (SB02, SB04) | Publication evidence, untrusted input, and diff trimming (07--09) | Skill manifests and role selection (T07--T09) | V5-01 completed: implemented feedback-to-Skill candidates with learned guidance and traceable artifact identity. |
| Xinyu Zhang | Configuration and webhook deduplication (SB-01, SB-07) | Frontend and comparison entry (SB10--SB11) | Repair-policy and patch work packages (10--12) | Tenant isolation and tool permissions (T10--T12) | V5-03 completed: checked candidate gates, tenant boundaries, activation/rollback and regression evidence. |
| Jiexuan Shen | Asynchronous task lifecycle (SB-06) | Workflow design (SB01, SB03, SB05) | Verification gate and reporting (13--15) | Task budgets, checkpoints and cancellation (T13--T15) | V5-06 completed: integrated member outputs and reconciled runtime, source identity and completed process records. |

The team confirms completion of allocated V1–V5 work. Each member handed their outputs to Jiexuan Shen for integration and centralized GitHub submission. Individual allocation is recorded by the backlogs and team confirmation, and each member recorded 36 hours. Backgrounds and interests are included in the updated report. The member statements and reflections were confirmed by the user and are included in the local report; those report materials are intentionally withheld from this upload.

## Actual effort across five versions

These are team-confirmed actual hours, not story points or the remaining-work estimates. V1 belongs to Sprint 1; V2/V3 to Sprint 2; V4/V5 to Sprint 3. The version and team totals match the supplied contribution table.

| Member | V1 | V2 | V3 | V4 | V5 | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Jiexuan Shen | 5 | 8 | 10 | 8 | 5 | 36 |
| Jiayu Zhu | 5 | 6 | 12 | 6 | 7 | 36 |
| Siye Tu | 5 | 6 | 10 | 7 | 8 | 36 |
| Tianyi Jiang | 6 | 6 | 10 | 8 | 6 | 36 |
| Jianyu Zhou | 4 | 6 | 14 | 6 | 6 | 36 |
| Xinyu Zhang | 4 | 8 | 12 | 8 | 4 | 36 |
| Team total | 29 | 40 | 68 | 43 | 36 | 216 |

Sprint totals are 29, 108 and 79 hours. Each member contributed 16.67% of team hours, with a relative contribution factor of 1.00.

## Completed V5 contributions

The owners and completed scope below follow the team-confirmed [V5 backlog, Review and Retrospective](V5-Sprint-Backlog-Review-Retrospective.md). Source and test evidence establishes project behavior; the allocation and member handoffs establish individual responsibility. The latest reruns validate the integrated product and do not imply that one person executed every later verification command.

| Task / member | V5 hours | Completed work | Verification evidence |
| --- | ---: | --- | --- |
| V5-01 / Siye Tu | 8 | Converted scoped feedback into versioned Skill candidates, embedded learned guidance and retained candidate provenance. | [auto_propose](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/evoagent/skill_evolution.py#L410); [build_candidate_artifact](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/evoagent/skill_evolution.py#L204); [test_auto_evolution_writes_learned_guidance_into_skill_md](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/tests/test_skill_evolution.py#L200) |
| V5-02 / Jianyu Zhou | 6 | Prepared repository-isolated train/validation/holdout evaluation and the static/evolved/random-feedback comparison; retained the negative Skill result. | [prepare_controlled_experiment_cases](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/evoagent/evaluation_experiments.py#L54); [test_skill_evolution_uses_train_validation_and_locked_holdout](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/tests/test_evaluation_experiments.py#L185); [current raw evaluation](../evidence/evaluation/current-source-20261127/controlled-evaluation.json) |
| V5-03 / Xinyu Zhang | 4 | Verified validation rejection, tenant isolation, controlled publication and rollback behavior; retained regression and rejected-action evidence. | [test_active_agent_skills_are_tenant_isolated_and_override_disk](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/tests/test_skill_evolution.py#L239); [test_holdout_regression_blocks_activation_without_leaking_case_details](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/tests/test_advanced.py#L207); [test_canary_assignment_and_error_budget_rollback](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/tests/test_production_features.py#L154) |
| V5-04 / Tianyi Jiang | 6 | Maintained reproducible setup, dependency instructions and fixture packaging, with source identities for the extracted release. | [Run guide](../RUN-AND-VERIFY.md); [dependency record](../evidence/release/latest-source-dependencies.txt); [89-test run and archive hash](../evidence/release/latest-source-test-run.json) |
| V5-05 / Jiayu Zhu | 7 | Prepared the demonstration flow and user-facing verification of coverage, budget pause, resume and revision-specific confirmation. | [test_budget_pause_resumes_only_unfinished_and_confirmation_is_idempotent](https://github.com/Theo-sssssss/CS5351-Project/blob/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5/tests/test_batched_review.py#L145); [archived deterministic walkthrough](../evidence/evaluation/demo-trace.json) |
| V5-06 / Jiexuan Shen | 5 | Integrated all member outputs, performed centralized repository submission, and consolidated current runtime, release identity and completed Scrum records. | [Uploaded source](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5); [completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md); [current source identity](../evidence/release/current-delivery-update.json) |

## Verification scope and attribution

The refreshed V5 source is commit `e48ee634b7f609a89f761adc8b7a516cb8fcba31`. Its 99 distributable source files match the tested archive; the repository adds `VERSION_SCOPE.md` and `EVALUATION_RESULTS.md` as descriptive files. The archive passed 89 tests under Python 3.11.5 on 27 November. The rerun used a fresh extraction and an existing dependency environment, not a fresh dependency installation.

On the 100-case simulated offline comparison, full-workflow aggregate precision/recall/F1 were 100.00% / 82.50% / 90.41%; on the separate 20-case holdout they were 100.00% / 62.50% / 76.92%. Evolving the Skill gave zero matched holdout gain. The prompt replay passed its numerical check but production activation remained blocked by provenance. These are fixture results without real LLM calls. The archived public-PR pilot is separate execution evidence.

Members supplied their outputs to Jiexuan Shen for integration and centralized GitHub upload. A single uploader is therefore not a statement of sole authorship. No individual commit history or unrecorded ceremony decision is invented. The confirmed personal statements and report remain local at the user's request.

## Repository workbooks

- [V1](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/EvoAgent_V1_Sprint_Backlog.xlsx)
- [V2](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/EvoAgent-V2-Sprint-Backlog.xlsx)
- [V3](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/Sprint_Backlog_V3.xlsx)
- [V4](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/Sprint_Backlog_V4.xlsx)
