# EvoAgent V1 Review — Sprint 1

Group 04. Team name: **group**.

- Global version: **V1**; course Sprint: **Sprint 1**.
- Sprint period: 7 September–4 October 2026.
- Related course Review / Retrospective: 2 October 2026.
- Source upload: 13 September 2026; restored source uploaded 22 September.
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Increment goal and scope

**Single-call pull-request review baseline.** One configured model call per review, PR intake, asynchronous task storage and a structured report. V1 is not an agent runtime and does not implement specialist collaboration, memory, Skills or checkpoint resume.

## Completed work supported by the snapshot

| Work area | Retained implementation |
| --- | --- |
| PR submission and retrieval | Manual PR URL entry and supported signed webhook events feed diff retrieval and a background task. |
| Review and report contract | One OpenAI-compatible model request returns JSON normalized into findings with severity, location, evidence, explanation, fix and suggested test. |
| Persistence and interface | SQLite-backed tasks expose review state and saved reports through the local dashboard/API. |
| Optional GitHub delivery | Summary posting is configurable; generating a report and proving live external delivery are separate checks. |

## Member allocation and actual effort

The following ownership and hours follow the team-confirmed backlogs and contribution table. Members handed outputs to Jiexuan Shen for integration and centralized GitHub submission; uploader identity is not sole-authorship evidence.

| Member | V1 actual hours | Assigned contribution |
| --- | ---: | --- |
| Jiexuan Shen | 5 | SB-06: asynchronous task lifecycle |
| Jiayu Zhu | 5 | SB-04: pull-request URL validation |
| Siye Tu | 5 | SB-02: local HTTP service and dashboard hosting |
| Tianyi Jiang | 6 | SB-05: PR metadata and diff retrieval |
| Jianyu Zhou | 4 | SB-03 / SB-08: artifact handling and baseline model call |
| Xinyu Zhang | 4 | SB-01 / SB-07: configuration and webhook deduplication |
| Team total | **29** | Actual effort for this version |

Each member recorded 36 hours across the complete V1–V5 project. These version hours are not the reductions in estimated remaining work. Full allocation is in [Contribution Traceability](Contribution-Traceability.md).

## Verification evidence

| Behavior | Source test |
| --- | --- |
| Fenced JSON parsing | [test_json_in_fence_is_accepted](https://github.com/Theo-sssssss/CS5351-Project/blob/258b304f041af6457af73f247838c84aef9e013d/src/sprint1/week1/EvoAgent_v1/tests/test_server.py#L7) |
| Normalized and sorted structured findings | [test_report_is_normalized_and_sorted](https://github.com/Theo-sssssss/CS5351-Project/blob/258b304f041af6457af73f247838c84aef9e013d/src/sprint1/week1/EvoAgent_v1/tests/test_server.py#L11) |

The [archived V1 regression](../evidence/regression/EvoAgent_v1-tests.txt) records **2 passing tests**. [Run metadata](../evidence/regression/test-runs.json) dates the retrospective check to **21 November 2026**. This document introduces no new test execution or real-model measurement. Those later tests verify the recovered snapshot rather than dating its original Sprint acceptance.

## Review discussion and outcome

The baseline established the service/provider/report boundaries before collaboration was introduced. Reviewing one frozen input with a stable report schema makes later comparisons interpretable. The retained two-test run covers parsing and normalization, so it cannot establish historical live GitHub integration, model accuracy or a full end-to-end acceptance demonstration.

**Recorded outcome:** The source and archived two-test result establish the documented baseline and its tested output contract. The original Sprint 1 formal acceptance decision, live-provider demonstration and reviewer sign-off are not retained. They are not inferred from an upload or calendar screenshot.

## References and next increment

- [Pinned V1 source](https://github.com/Theo-sssssss/CS5351-Project/tree/258b304f041af6457af73f247838c84aef9e013d/src/sprint1/week1/EvoAgent_v1)
- [Version backlog](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/docs/EvoAgent_V1_Sprint_Backlog.xlsx)
- [Course Sprint record](Sprint-1-Records.md)
- [V1 Retrospective](V1-Retrospective.md)
- [Repository and evaluation evidence](Evidence-Index.md)

Keep V1 as the recoverable single-call baseline. For a new comparative study, use identical frozen changes and record provider configuration, findings, failures and delivery state. These are forward verification needs, not a newly asserted historical meeting decision.
