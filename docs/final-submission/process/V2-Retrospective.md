# EvoAgent V2 Retrospective — Sprint 2

Group 04. Team name: **group**.

- Global version: **V2**; course Sprint: **Sprint 2**.
- Sprint period: 12 October–8 November 2026.
- Related course Review / Retrospective: 6 November 2026.
- Source upload: 18 October 2026.
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Purpose and evidence basis

This is a version-specific technical retrospective linked to the [V2 Review](V2-Review.md) and the [course Sprint account](Sprint-2-Records.md). It records lessons supported by implementation, archived verification and the team-confirmed work allocation. Later responses are identified as later outcomes; unrecorded historical votes, a separate version meeting date and individual approvals are not invented.

## What worked, what needed improvement, and responses

| Observation | Evidence or issue | Completed later response / retained practice | Responsible contributors |
| --- | --- | --- | --- |
| Explicit roles made the workflow inspectable. | Role traces and attributions can be checked independently of final prose. | Preserve the topology and report contract when introducing tools. | Jiexuan Shen and Siye Tu |
| Additional calls increased execution and failure paths. | Fixed collaboration creates more intermediate states than the one-call baseline. | V3 added programmatic tool permissions, step/call/token/time budgets and recovery. | Tianyi Jiang and Jianyu Zhou |
| Evidence validity did not equal defect validity. | The gate checks source correspondence; semantic accuracy still requires labelled data. | Retain false comments and matched findings in later evaluation rather than claiming quality from topology alone. | Jianyu Zhou |
| Review completion and GitHub delivery were separate. | The persistence test preserves a report when comment posting fails. | Keep distinct delivery states and observable errors in later integration. | Jiayu Zhu and Xinyu Zhang |

## Process and collaboration lessons

V2 accounted for **40 actual team hours**. The named assignments and centralized handoffs make responsibility traceable alongside the integrated source. The table in [Contribution Traceability](Contribution-Traceability.md) records all version totals and each member's 36-hour project total. A single GitHub uploader does not replace those contribution records.

The useful retrospective question is which interface or evidence made the next increment easier to verify. A passing suite establishes the covered contracts; it does not establish that a larger workflow has better review accuracy. Preserve rejected actions, failed runs and uncertainty about historical demonstrations so later members can distinguish implemented behavior from an attractive but unsupported result.

## Follow-up and completion boundary

Use V3 to evaluate bounded inspection and checkpoint reuse under the same frozen diff and declared resources. Record completion, failures and usage alongside finding quality. A common real-PR benchmark is still needed to compare review accuracy.

The archived 33-test run supports the recovered V2 snapshot. Original formal sign-off and the exact live PR/model configuration demonstrated on 6 November are not retained. The later V3 upload is Sprint-end follow-up and is not treated as a V2 Review demonstration.

## Scheduled discussion evidence

The following screenshots record scheduled appointments in the course Sprint. Team attendance confirmation and technical outcomes are separate evidence. They are not transcripts of the version Review or Retrospective.

| Course week | Scheduled date | Screenshot |
| --- | --- | --- |
| Week 06 | 2026-10-16 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/ea1c3e7bcaf0f61dfb04b0d11ab57b384567b037/docs/evidence/05_Week06_10%E6%9C%8816%E6%97%A5.jpg) |
| Week 07 | 2026-10-23 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/ea1c3e7bcaf0f61dfb04b0d11ab57b384567b037/docs/evidence/06_Week07_10%E6%9C%8823%E6%97%A5.jpg) |
| Week 08 | 2026-10-30 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/ea1c3e7bcaf0f61dfb04b0d11ab57b384567b037/docs/evidence/07_Week08_10%E6%9C%8830%E6%97%A5.jpg) |
| Week 09 | 2026-11-06 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/ea1c3e7bcaf0f61dfb04b0d11ab57b384567b037/docs/evidence/08_Week09_11%E6%9C%886%E6%97%A5.jpg) |

See the [complete screenshot index](https://github.com/Theo-sssssss/CS5351-Project/tree/main/docs/evidence) and [V2 Review](V2-Review.md) for source/test links. The current V5 verification and experiments remain in their own records; their test count and metrics are not substituted for V2.
