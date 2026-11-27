# EvoAgent V3 Retrospective — Sprint 2

Group 04. Team name: **group**.

- Global version: **V3**; course Sprint: **Sprint 2**.
- Sprint period: 12 October–8 November 2026.
- Related course Review / Retrospective: 6 November 2026 (course ceremony); V3 source followed on 7 November.
- Source upload: 7 November 2026.
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Purpose and evidence basis

This is a version-specific technical retrospective linked to the [V3 Review](V3-Review.md) and the [course Sprint account](Sprint-2-Records.md). It records lessons supported by implementation, archived verification and the team-confirmed work allocation. Later responses are identified as later outcomes; unrecorded historical votes, a separate version meeting date and individual approvals are not invented.

## What worked, what needed improvement, and responses

| Observation | Evidence or issue | Completed later response / retained practice | Responsible contributors |
| --- | --- | --- | --- |
| Read-only tool contracts limited authority. | Tool permissions and argument validation are checked before execution. | V4 retained bounded context and added repository-scoped memory and role-scoped Skills. | Jianyu Zhou, Tianyi Jiang and Siye Tu |
| Checkpoints made interruption explicit. | Completed work can be reused without rerunning finished calls. | Later integration added batch coverage and revision-specific confirmation. | Tianyi Jiang, Jiexuan Shen and Jiayu Zhu |
| Synthesis could damage valid findings. | Model-produced summaries must not silently replace approved evidence records. | Preserve structured findings separately from summary prose and keep integrity regression tests. | Siye Tu and Jiexuan Shen |
| A richer runtime did not establish better accuracy. | The 54-test run uses controlled dependencies and does not score real reviewer correctness. | Retain controlled experiments and explicitly scoped model pilots in later versions. | Jianyu Zhou |

## Process and collaboration lessons

V3 accounted for **68 actual team hours**. The named assignments and centralized handoffs make responsibility traceable alongside the integrated source. The table in [Contribution Traceability](Contribution-Traceability.md) records all version totals and each member's 36-hour project total. A single GitHub uploader does not replace those contribution records.

The useful retrospective question is which interface or evidence made the next increment easier to verify. A passing suite establishes the covered contracts; it does not establish that a larger workflow has better review accuracy. Preserve rejected actions, failed runs and uncertainty about historical demonstrations so later members can distinguish implemented behavior from an attractive but unsupported result.

## Follow-up and completion boundary

Evaluate V4 bounded context, scoped feedback and declarative Skills without expanding tools to arbitrary repository modification. Keep compatible-input checks and report coverage observable. Any automatic-repair claim needs its own before/after and verification evidence.

The archived 54-test result verifies the recovered V3 test scope. No separate V3 Review date or version-specific formal sign-off was supplied, and a pre-upload demonstration on 6 November is not established. V3 remains within Sprint 2; the version folder name does not create a third course Sprint.

## Scheduled discussion evidence

The following screenshots record scheduled appointments in the course Sprint. Team attendance confirmation and technical outcomes are separate evidence. They are not transcripts of the version Review or Retrospective.

| Course week | Scheduled date | Screenshot |
| --- | --- | --- |
| Week 06 | 2026-10-16 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-06-2026-10-16.jpg) |
| Week 07 | 2026-10-23 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-07-2026-10-23.jpg) |
| Week 08 | 2026-10-30 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-08-2026-10-30.jpg) |
| Week 09 | 2026-11-06 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-09-2026-11-06.jpg) |

See the [complete screenshot index](https://github.com/Theo-sssssss/CS5351-Project/tree/main/docs/evidence) and [V3 Review](V3-Review.md) for source/test links. The current V5 verification and experiments remain in their own records; their test count and metrics are not substituted for V3.
