# EvoAgent V2 Review — Sprint 2

Group 04. Team name: **group**.

- Global version: **V2**; course Sprint: **Sprint 2**.
- Sprint period: 12 October–8 November 2026.
- Related course Review / Retrospective: 6 November 2026.
- Source upload: 18 October 2026.
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Increment goal and scope

**Fixed collaboration and diff-evidence checks.** Fixed Lead, Security Worker, Correctness/Reliability Worker, Critic and synthesis workflow. V2 retains a one-call baseline mode and a fixed five-call collaborative mode. Autonomous tool loops, repository memory, Skills and checkpoint resume belong to later increments.

## Completed work supported by the snapshot

| Work area | Retained implementation |
| --- | --- |
| Fixed collaboration | Lead planning, two specialists, Critic checking and final synthesis produce inspectable role traces. |
| Comparable execution modes | Baseline and collaborative tasks share GitHub intake, SQLite storage, report fields and finding gates. |
| Evidence gate | Findings require a valid changed-file path, added-line location and matching evidence; duplicates are normalized. |
| Usage and delivery visibility | Role states and model usage are recorded. GitHub delivery failures preserve a successful stored report. |

## Member allocation and actual effort

The following ownership and hours follow the team-confirmed backlogs and contribution table. Members handed outputs to Jiexuan Shen for integration and centralized GitHub submission; uploader identity is not sole-authorship evidence.

| Member | V2 actual hours | Assigned contribution |
| --- | ---: | --- |
| Jiexuan Shen | 8 | SB01 / SB03 / SB05: workflow design |
| Jiayu Zhu | 6 | SB07–SB08: platform integration |
| Siye Tu | 6 | SB02 / SB04: model and worker integration |
| Tianyi Jiang | 6 | SB13–SB15: QA and Scrum tracking |
| Jianyu Zhou | 6 | SB06 / SB09 / SB12: review integrity and reporting safeguards |
| Xinyu Zhang | 8 | SB10–SB11: frontend and comparison entry |
| Team total | **40** | Actual effort for this version |

Each member recorded 36 hours across the complete V1–V5 project. These version hours are not the reductions in estimated remaining work. Full allocation is in [Contribution Traceability](Contribution-Traceability.md).

## Verification evidence

| Behavior | Source test |
| --- | --- |
| Fixed five-role collaboration | [test_collaborative_uses_five_roles](https://github.com/Theo-sssssss/CS5351-Project/blob/f2315543fd577c573d1e629d9e39750107047a40/src/sprint2/week1/EvoAgent_v2/tests/test_workflow_and_app.py#L86) |
| Aggregate model-usage accounting | [test_tokens_are_summed](https://github.com/Theo-sssssss/CS5351-Project/blob/f2315543fd577c573d1e629d9e39750107047a40/src/sprint2/week1/EvoAgent_v2/tests/test_workflow_and_app.py#L103) |
| Reject mismatched source quotations | [test_rejects_wrong_evidence](https://github.com/Theo-sssssss/CS5351-Project/blob/f2315543fd577c573d1e629d9e39750107047a40/src/sprint2/week1/EvoAgent_v2/tests/test_diff_and_gates.py#L75) |
| Separate review completion from posting failure | [test_delivery_failure_preserves_success_report](https://github.com/Theo-sssssss/CS5351-Project/blob/f2315543fd577c573d1e629d9e39750107047a40/src/sprint2/week1/EvoAgent_v2/tests/test_store.py#L24) |

The [archived V2 regression](../evidence/regression/EvoAgent_v2-tests.txt) records **33 passing tests**. [Run metadata](../evidence/regression/test-runs.json) dates the retrospective check to **21 November 2026**. This document introduces no new test execution or real-model measurement. Those later tests verify the recovered snapshot rather than dating its original Sprint acceptance.

## Review discussion and outcome

The Review can examine V2 because its source and backlog preceded 6 November. The important distinction is between role coordination, source correspondence and semantic correctness. A Critic or valid quotation can make a finding inspectable without proving that the claimed defect is real. Fixed-call topology tests validate workflow wiring rather than a quality improvement from multiple agents.

**Recorded outcome:** The archived 33-test run supports the recovered V2 snapshot. Original formal sign-off and the exact live PR/model configuration demonstrated on 6 November are not retained. The later V3 upload is Sprint-end follow-up and is not treated as a V2 Review demonstration.

## References and next increment

- [Pinned V2 source](https://github.com/Theo-sssssss/CS5351-Project/tree/f2315543fd577c573d1e629d9e39750107047a40/src/sprint2/week1/EvoAgent_v2)
- [Version backlog](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/docs/EvoAgent-V2-Sprint-Backlog.xlsx)
- [Course Sprint record](Sprint-2-Records.md)
- [V2 Retrospective](V2-Retrospective.md)
- [Repository and evaluation evidence](Evidence-Index.md)

Use V3 to evaluate bounded inspection and checkpoint reuse under the same frozen diff and declared resources. Record completion, failures and usage alongside finding quality. A common real-PR benchmark is still needed to compare review accuracy.
