# EvoAgent V4 Review — Sprint 3

Group 04. Team name: **group**.

- Global version: **V4**; course Sprint: **Sprint 3**.
- Sprint period: 9–30 November 2026.
- Related course Review / Retrospective: 27 November 2026 (Sprint 3 completion checkpoint).
- Source upload: 21 November 2026 (restored snapshot).
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Increment goal and scope

**Adaptive context, scoped memory and declarative Skills.** V4 is the adaptive-review increment: risk-aware bounded context, repository-scoped review memory and feedback recall, declarative role-scoped Skills, and the bounded runtime/evidence gates supporting them. The restored snapshot includes shared later infrastructure; its presence does not make controlled Skill evolution a newly delivered V4 feature.

## Completed work supported by the snapshot

| Work area | Retained implementation |
| --- | --- |
| Adaptive context | Risk-aware selection bounds the changed-code material supplied to reviewers and preserves evidence-bearing information. |
| Scoped feedback memory | Recall is constrained by repository and tenant, with expiry and separate role/runtime state. |
| Declarative Skills | Manifests describe role scope, instructions and tool permissions; discovery and validation reject invalid configuration. |
| Integrated execution boundary | Budget enforcement, checkpoints and publication evidence checks remain part of the integrated workflow. |

## Member allocation and actual effort

The following ownership and hours follow the team-confirmed backlogs and contribution table. Members handed outputs to Jiexuan Shen for integration and centralized GitHub submission; uploader identity is not sole-authorship evidence.

| Member | V4 actual hours | Assigned contribution |
| --- | ---: | --- |
| Jiexuan Shen | 8 | T13–T15: task budgets, checkpoints and cancellation |
| Jiayu Zhu | 6 | T16–T18: adaptive integration and release handoff |
| Siye Tu | 7 | T07–T09: Skill manifests and role selection |
| Tianyi Jiang | 8 | T01–T03: risk ranking and bounded diff context |
| Jianyu Zhou | 6 | T04–T06: scoped memory, recall and expiry |
| Xinyu Zhang | 8 | T10–T12: tenant isolation and tool permissions |
| Team total | **43** | Actual effort for this version |

Each member recorded 36 hours across the complete V1–V5 project. These version hours are not the reductions in estimated remaining work. Full allocation is in [Contribution Traceability](Contribution-Traceability.md).

## Verification evidence

| Behavior | Source test |
| --- | --- |
| Risk-aware bounded context | [test_large_diff_uses_risk_ranked_hunk_map_reduce](https://github.com/Theo-sssssss/CS5351-Project/blob/7a866faddaca3d715b987a1325bf7f2a7772ca5d/src/sprint4/week1/EvoAgent_v4/tests/test_context_manager.py#L73) |
| Repository/tenant recall isolation | [test_memory_recall_is_repository_and_tenant_isolated](https://github.com/Theo-sssssss/CS5351-Project/blob/7a866faddaca3d715b987a1325bf7f2a7772ca5d/src/sprint4/week1/EvoAgent_v4/tests/test_runtime_memory_context.py#L63) |
| Feedback expiry | [test_memory_recall_purges_expired_records](https://github.com/Theo-sssssss/CS5351-Project/blob/7a866faddaca3d715b987a1325bf7f2a7772ca5d/src/sprint4/week1/EvoAgent_v4/tests/test_runtime_memory_context.py#L83) |
| Skill manifest validation | [test_skill_md_requires_frontmatter_and_matching_directory_name](https://github.com/Theo-sssssss/CS5351-Project/blob/7a866faddaca3d715b987a1325bf7f2a7772ca5d/src/sprint4/week1/EvoAgent_v4/tests/test_skill_evolution.py#L157) |

The [initial V4 log](../evidence/regression/EvoAgent_v4-tests.txt) records 70 tests with **one failure and five errors**. The [post-maintenance log](../evidence/regression/EvoAgent_v4-after-tests.txt) records **70 passing tests**, with remaining database-closure ResourceWarnings. The [post-maintenance fingerprints](../evidence/regression/EvoAgent_v4-after-sha256.json) identify the maintained copy. The old repository revision and repaired local copy are separate source identities; this document introduces no fresh V4 test run.

## Review discussion and outcome

The Review considers the adaptive-review scope against the V4 version statement, named backlog packages and retained tests. The initial recovered regression failed because fixture files were missing and an assertion depended on quotation style. The maintained local copy restored the fixtures and compared the supported Python assignment structurally. The before/after results and source fingerprints make that maintenance traceable.

**Recorded outcome:** V4 is included in the team-confirmed completed Sprint 3 prototype scope. The archived maintained local copy passed 70 tests. That result must not be presented as a fresh successful run of the unchanged 7a866fa repository snapshot, nor as a separate V4-only acceptance vote. V5 controlled evolution and the current 89-test source have their own records.

## References and next increment

- [Pinned V4 source](https://github.com/Theo-sssssss/CS5351-Project/tree/7a866faddaca3d715b987a1325bf7f2a7772ca5d/src/sprint4/week1/EvoAgent_v4)
- [Version backlog](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/docs/Sprint_Backlog_V4.xlsx)
- [Course Sprint record](Sprint-3-Records.md)
- [V4 Retrospective](V4-Retrospective.md)
- [Repository and evaluation evidence](Evidence-Index.md)
- [V4 intended scope](https://github.com/Theo-sssssss/CS5351-Project/blob/7a866faddaca3d715b987a1325bf7f2a7772ca5d/src/sprint4/week1/EvoAgent_v4/VERSION_SCOPE.md)
- [Completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md)

Use V5 to evaluate feedback-driven candidates on fixed partitions and keep numerical improvement separate from production provenance and publication. Preserve blocked and negative outcomes. Clean installation and deployment-specific checks remain separate from archive regression.
