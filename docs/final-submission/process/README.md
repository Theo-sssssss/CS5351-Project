# EvoAgent Scrum Records

Group 04. Team name: **group**. Documentation updated on 28 November 2026; the completed Sprint 3 Review and Retrospective checkpoint remains 27 November.

These records describe three course Sprints and five version increments. The team supplied the periods, ceremony dates, participant roster, contribution allocation and remaining-work estimates. Sprint 1 and Sprint 2 technical discussions are retrospective reconstructions where original decisions were not retained. Sprint 3 and V5 include the team-confirmed completion account.

## Team and attribution

Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang. The team confirmed attendance for meetings already held and completion of allocated work. Each member recorded 36 hours, for 216 team hours. Member outputs were handed to Jiexuan Shen for integration and centralized submission. See [contribution traceability](Contribution-Traceability.md) for named tasks, version hours and completed V5 evidence.

## Sprint and ceremony dates

| Sprint | Team-confirmed period | Increments | Planning | Review / Retrospective |
| --- | --- | --- | --- | --- |
| 1 | 7 September–4 October 2026 | V1 | 7 September | 2 October |
| 2 | 12 October–8 November 2026 | V2, V3 | 12 October | 6 November |
| 3 | 9–30 November 2026 | V4, V5 and integrated delivery | 9 November | 27 November |

The team specifies development from Week 2 through Week 12. Version folders named `sprint1` through `sprint5` identify five increments, not five course Sprints. V3 was uploaded on 7 November after the Sprint 2 Review, so its upload is Sprint-end follow-up evidence.

## Records and evidence

- [Sprint 1 Planning, Review and Retrospective](Sprint-1-Records.md)
- [Sprint 2 Planning, Review and Retrospective](Sprint-2-Records.md)
- [Sprint 3 Planning, completed Review and Retrospective](Sprint-3-Records.md)
- [Completed V5 backlog, Review and Retrospective](V5-Sprint-Backlog-Review-Retrospective.md)
- [Contribution traceability and actual version hours](Contribution-Traceability.md)
- [Repository, test and evaluation evidence index](Evidence-Index.md)
- [Weekly discussion screenshots](https://github.com/Theo-sssssss/CS5351-Project/tree/main/docs/evidence)

The 12 supplied calendar screenshots cover Weeks 02–13. They record scheduled entries; attendance confirmations and discussion outcomes are separate evidence. The scheduled entries show 15:00–18:00, GMT+8, at AC5-302. Planning, Review and Retrospective start times were not supplied and are not inferred from those appointments.

## Version-specific Review and Retrospective records

These eight files use the global V1–V4 numbering. The course grouping remains unchanged; the original V5 combined completion record is retained separately.

| Global version | Course Sprint | Review | Retrospective |
| --- | --- | --- | --- |
| V1 | Sprint 1 | [V1 Review](V1-Review.md) | [V1 Retrospective](V1-Retrospective.md) |
| V2 | Sprint 2 | [V2 Review](V2-Review.md) | [V2 Retrospective](V2-Retrospective.md) |
| V3 | Sprint 2 | [V3 Review](V3-Review.md) | [V3 Retrospective](V3-Retrospective.md) |
| V4 | Sprint 3 | [V4 Review](V4-Review.md) | [V4 Retrospective](V4-Retrospective.md) |
| V5 | Sprint 3 | [Completed V5 Review / Retrospective](V5-Sprint-Backlog-Review-Retrospective.md) | Same combined record |

V3's source upload on 7 November follows the 6 November Sprint 2 ceremony. Its version record is a retrospective technical account of Sprint-end follow-up, not a claim that the uploaded build was demonstrated at that ceremony. V4's archived post-maintenance pass identifies the repaired local copy separately from its original repository snapshot.

## Current source and verification

The current uploaded source is [V5 at e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5), uploaded on 28 November. Its 99 distributable source files match the [tested archive](../submission/EvoAgent-Final-Source.zip). The [current run](../evidence/release/latest-source-test-run.json) records 89 passing tests, zero failures and zero errors on 27 November with Python 3.11.5. Historical increment logs retain their original scope.

The [current-source offline rerun](../evidence/evaluation/current-source-20261127/README.md) reproduces the five-arm aggregate comparison and separately reports the 20-case holdout. It uses synthetic fixtures and simulated model clients. The evolved Skill did not improve matched holdout F1. The separate prompt replay passed numerical checks while its production provenance gate blocked activation. The old single-public-PR pilot is execution evidence, not labelled accuracy evidence.

## Remaining-work estimates and actual effort

| Milestone | Estimated remaining development work (hours) |
| --- | ---: |
| Project start | 216 |
| V1 complete | 186 |
| V2 complete | 132 |
| V3 complete | 72 |
| V4 complete | 30 |
| V5 complete | 0 |

These team-reported estimates differ from the actual effort allocation: V1–V5 used 29, 40, 68, 43 and 36 hours; course Sprint totals were 29, 108 and 79 hours. The zero estimate covers the documented development scope and does not imply that presentation rehearsal, report revision or official submission has finished. Upload dates are timeline proxies and do not establish individual version completion or ceremony acceptance dates.

## Delivery follow-up

The completed development records and non-report delivery files are on `main`. The report PDF, LaTeX source and personal report statements remain local at the user's request. Report section-length adjustments, separate report upload, presentation rehearsal, classroom setup and official submission remain delivery tasks. Video inspection was waived and website translation remains deferred.
