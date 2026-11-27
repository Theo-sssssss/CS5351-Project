# EvoAgent V1 Retrospective — Sprint 1

Group 04. Team name: **group**.

- Global version: **V1**; course Sprint: **Sprint 1**.
- Sprint period: 7 September–4 October 2026.
- Related course Review / Retrospective: 2 October 2026.
- Source upload: 13 September 2026; restored source uploaded 22 September.
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Purpose and evidence basis

This is a version-specific technical retrospective linked to the [V1 Review](V1-Review.md) and the [course Sprint account](Sprint-1-Records.md). It records lessons supported by implementation, archived verification and the team-confirmed work allocation. Later responses are identified as later outcomes; unrecorded historical votes, a separate version meeting date and individual approvals are not invented.

## What worked, what needed improvement, and responses

| Observation | Evidence or issue | Completed later response / retained practice | Responsible contributors |
| --- | --- | --- | --- |
| A small baseline made interfaces understandable. | The PR-to-task-to-report contract can be inspected without additional agent state. | Retain the same input/output contract in subsequent versions. | Jiexuan Shen and Tianyi Jiang |
| One model response lacked independent challenge. | A plausible finding could still need a separate location/evidence check. | V2 introduced specialist proposals, Critic review and programmatic evidence gates. | Jiexuan Shen, Siye Tu and Jianyu Zhou |
| Parser tests were narrower than review acceptance. | Two passing tests do not measure review correctness or provider integration. | Later versions added workflow, rejected-evidence and scoped-runtime tests; real-PR accuracy remains a separate study. | Tianyi Jiang and Jianyu Zhou |
| Optional external posting needed a distinct outcome. | A useful stored report should not be confused with successful comment delivery. | V2 retained report success separately from delivery failure. | Jiayu Zhu and Jianyu Zhou |

## Process and collaboration lessons

V1 accounted for **29 actual team hours**. The named assignments and centralized handoffs make responsibility traceable alongside the integrated source. The table in [Contribution Traceability](Contribution-Traceability.md) records all version totals and each member's 36-hour project total. A single GitHub uploader does not replace those contribution records.

The useful retrospective question is which interface or evidence made the next increment easier to verify. A passing suite establishes the covered contracts; it does not establish that a larger workflow has better review accuracy. Preserve rejected actions, failed runs and uncertainty about historical demonstrations so later members can distinguish implemented behavior from an attractive but unsupported result.

## Follow-up and completion boundary

Keep V1 as the recoverable single-call baseline. For a new comparative study, use identical frozen changes and record provider configuration, findings, failures and delivery state. These are forward verification needs, not a newly asserted historical meeting decision.

The source and archived two-test result establish the documented baseline and its tested output contract. The original Sprint 1 formal acceptance decision, live-provider demonstration and reviewer sign-off are not retained. They are not inferred from an upload or calendar screenshot.

## Scheduled discussion evidence

The following screenshots record scheduled appointments in the course Sprint. Team attendance confirmation and technical outcomes are separate evidence. They are not transcripts of the version Review or Retrospective.

| Course week | Scheduled date | Screenshot |
| --- | --- | --- |
| Week 02 | 2026-09-11 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-02-2026-09-11.jpg) |
| Week 03 | 2026-09-18 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-03-2026-09-18.jpg) |
| Week 04 | 2026-09-25 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-04-2026-09-25.jpg) |
| Week 05 | 2026-10-02 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-05-2026-10-02.jpg) |

See the [complete screenshot index](https://github.com/Theo-sssssss/CS5351-Project/tree/main/docs/evidence) and [V1 Review](V1-Review.md) for source/test links. The current V5 verification and experiments remain in their own records; their test count and metrics are not substituted for V1.
