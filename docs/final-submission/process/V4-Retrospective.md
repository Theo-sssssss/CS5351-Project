# EvoAgent V4 Retrospective — Sprint 3

Group 04. Team name: **group**.

- Global version: **V4**; course Sprint: **Sprint 3**.
- Sprint period: 9–30 November 2026.
- Related course Review / Retrospective: 27 November 2026 (Sprint 3 completion checkpoint).
- Source upload: 21 November 2026 (restored snapshot).
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Purpose and evidence basis

This is a version-specific technical retrospective linked to the [V4 Review](V4-Review.md) and the [course Sprint account](Sprint-3-Records.md). It records lessons supported by implementation, archived verification and the team-confirmed work allocation. Later responses are identified as later outcomes; unrecorded historical votes, a separate version meeting date and individual approvals are not invented.

## What worked, what needed improvement, and responses

| Observation | Evidence or issue | Completed later response / retained practice | Responsible contributors |
| --- | --- | --- | --- |
| Context, memory and Skills made review configuration explicit. | The V4 scope and tests identify risk selection, recall boundaries, expiry and manifest rules. | Keep these interfaces independently testable as V5 adds controlled candidate evolution. | Tianyi Jiang, Jianyu Zhou and Siye Tu |
| Missing fixtures prevented archive reproducibility. | The first 70-test run had one failure and five errors; the maintained copy later passed. | Distribute fixed datasets with the verified current source and retain file hashes and dependency records. | Tianyi Jiang and Xinyu Zhang |
| A quotation-sensitive assertion checked text rather than behavior. | Equivalent Python assignment quoting caused a false regression failure. | Use a structural assertion for the supported assignment while preserving unsupported statements. | Xinyu Zhang and the maintenance work package |
| Shared restored infrastructure could blur version claims. | The restored V4 tree contains modules used by later increments. | Use VERSION_SCOPE and separate V5 records for attribution; do not infer delivery order from every module in a restored snapshot. | Jiexuan Shen and Jiayu Zhu |
| Warnings remained visible after tests passed. | The post-maintenance log retains database-closure ResourceWarnings. | Treat cleanup as maintenance follow-up; a passing test run is not evidence that all operational debt is resolved. | Tianyi Jiang and Xinyu Zhang |

## Process and collaboration lessons

V4 accounted for **43 actual team hours**. The named assignments and centralized handoffs make responsibility traceable alongside the integrated source. The table in [Contribution Traceability](Contribution-Traceability.md) records all version totals and each member's 36-hour project total. A single GitHub uploader does not replace those contribution records.

The useful retrospective question is which interface or evidence made the next increment easier to verify. A passing suite establishes the covered contracts; it does not establish that a larger workflow has better review accuracy. Preserve rejected actions, failed runs and uncertainty about historical demonstrations so later members can distinguish implemented behavior from an attractive but unsupported result.

## Follow-up and completion boundary

Use V5 to evaluate feedback-driven candidates on fixed partitions and keep numerical improvement separate from production provenance and publication. Preserve blocked and negative outcomes. Clean installation and deployment-specific checks remain separate from archive regression.

V4 is included in the team-confirmed completed Sprint 3 prototype scope. The archived maintained local copy passed 70 tests. That result must not be presented as a fresh successful run of the unchanged 7a866fa repository snapshot, nor as a separate V4-only acceptance vote. V5 controlled evolution and the current 89-test source have their own records.

## Scheduled discussion evidence

The following screenshots record scheduled appointments in the course Sprint. Team attendance confirmation and technical outcomes are separate evidence. They are not transcripts of the version Review or Retrospective.

| Course week | Scheduled date | Screenshot |
| --- | --- | --- |
| Week 10 | 2026-11-13 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-10-2026-11-13.jpg) |
| Week 11 | 2026-11-20 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-11-2026-11-20.jpg) |
| Week 12 | 2026-11-27 | [Calendar entry](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-12-2026-11-27.jpg) |

See the [complete screenshot index](https://github.com/Theo-sssssss/CS5351-Project/tree/main/docs/evidence) and [V4 Review](V4-Review.md) for source/test links. The current V5 verification and experiments remain in their own records; their test count and metrics are not substituted for V4.
