# EvoAgent Sprint 3 Records

Group 04. Team name: **group**. Documentation updated on 28 November 2026; the completed Review and Retrospective remain dated 27 November.

Period: 9–30 November 2026, course Weeks 10–13.

Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou, and Xinyu Zhang.

Planning: 9 November 2026. Review and Retrospective completion account: 27 November 2026, as specified by the team. The Sprint closes on 30 November.

Status at the team-specified 27 November reporting checkpoint: documented development scope completed and accepted against the archived verification evidence. The participants are listed above. This account incorporates team confirmation and source inspection. See the [completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md) for task-level evidence.

## Weekly calendar evidence

| Course week | Scheduled date | Screenshot |
| --- | --- | --- |
| Week 10 | 2026-11-13 | [Calendar screenshot](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-10-2026-11-13.jpg) |
| Week 11 | 2026-11-20 | [Calendar screenshot](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-11-2026-11-20.jpg) |
| Week 12 | 2026-11-27 | [Calendar screenshot](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-12-2026-11-27.jpg) |

The [Week 13 / 4 December appointment](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-13-2026-12-04.jpg) is outside the stated 9–30 November Sprint period. Screenshots establish scheduled entries, while the team separately confirmed attendance and the 27 November completion account.

## Sprint Planning

Date: 9 November 2026.

### Goal

Complete adaptive review and controlled evolution, verify the delivery snapshot, and prepare reproducible evaluation, demonstration, and course submission materials.

### Selected work and acceptance criteria

| Work item | Related user story | Acceptance criteria |
| --- | --- | --- |
| Risk-aware bounded context | US08 | Context selection has a defined size, source, and selection rationale. |
| Repository feedback memory | US07, US08 | Confirmed feedback can be recalled within the correct tenant and repository scope. |
| Declarative Skills | US08 | Skill instructions, role scope, and tool permissions are validated. |
| Feedback and candidate generation | US07 | Feedback is linked to review evidence and candidate provenance is retained. |
| Validation and holdout replay | US07 | Fixed datasets, splits, metrics, and activation gates are recorded, including negative results. |
| Version publication and rollback | US07, US08 | Only eligible candidates can be published, and a prior eligible version can be restored. |
| Final integration and batch review | US01, US03, US05, US06, extended scope | Coverage, remaining budget, pause, resume, and report revision confirmation are inspectable. |
| Regression and delivery | Foundation | Source, test logs, report claims, demonstration mode, and release identity agree. |

### Remaining-work estimates

The team specifies development from Week 2 through Week 12, with 30 hours remaining after V4 and zero after V5. The Week 12 discussion and Sprint 3 completion account are dated 27 November. The zero-hour endpoint covers the team-reported development scope; final report completion, rehearsal, and submission are still tracked as delivery actions. Individual milestone completion days are not inferred from upload dates.

## Completed Sprint Review

Reporting date: 27 November 2026. The team accepted the documented prototype scope on the basis of the following archived results and completed work.

### Repository increments

| Snapshot | Uploaded date in GMT+8 | Repository evidence |
| --- | --- | --- |
| Restored V4 adaptive review | 21 November 2026 | [7a866fa](https://github.com/Theo-sssssss/CS5351-Project/commit/7a866faddaca3d715b987a1325bf7f2a7772ca5d) on `main` |
| Final-delivery integration snapshot | 21 November 2026 | [b9a63e3](https://github.com/Theo-sssssss/CS5351-Project/commit/b9a63e3097635cc5d6f6bad14b82732da43dba02) on `codex/evoagent-final-delivery` |
| Restored V5 controlled evolution | 23 November 2026 | [faf93a1](https://github.com/Theo-sssssss/CS5351-Project/commit/faf93a111f24bff749a8dc1c26c9aa56bddf2b88) on `main` |
| Verified V5 delivery refresh | 28 November 2026 | [e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5) on `main` |

V4 and V5 are restored snapshots containing shared infrastructure. Attribute their intended increments using their `VERSION_SCOPE.md` files rather than treating every included module as newly developed in that version.

The current source is [V5 at e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5). Its 99 source files match the tested archive; two repository description files sit alongside them. The earlier `b9a63e3` delivery and `faf93a1` V5 snapshot are historical references. Publishing the refresh on 28 November does not change the team's 27 November Review date.

### Technical results

The handoff logs record 70 passing tests for the repaired V4 snapshot and 70 for V5. The current delivery source passed 89 tests. The original V4 regression produced five missing-fixture errors and one quotation-sensitive assertion failure. Retaining the before-and-after logs makes this maintenance work traceable. These archived logs remain unchanged. A separate 27 November check of the refreshed source ZIP passed 89 tests after extraction; see `../evidence/release/latest-source-test-run.json`.

The final snapshot adds batch coverage, budget pause and resume, report confirmation, and a workbench separating evaluation readiness from publication.

### Evaluation results

The 27 November current-source rerun used the fixed 100-case synthetic corpus and simulated model clients, with no real LLM calls.

| Full workflow | Cases | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Aggregate: train + validation + holdout | 100 | 100.00% | 82.50% | 90.41% |
| Independent held-out subset | 20 | 100.00% | 62.50% | 76.92% |

The evolved Skill matched the full workflow: zero holdout F1 gain. The separate 130-case prompt replay improved fixture F1 from 66.67% to 100%; production activation remained blocked by data provenance despite numerical success. The [raw rerun and metadata](../evidence/evaluation/current-source-20261127/README.md) preserve the source/dataset hashes, commands and scope.

The archived real-model pilot processed one frozen, unlabelled documentation PR. Batched execution completed in 27.415 seconds with 9,262 recorded tokens; legacy execution exceeded its budget after 45.876 seconds. That pilot was not rerun and does not estimate review precision, recall or general reliability.

### Review verification and acceptance

The team confirmed completion of the allocated V5 work. V5 regression passed 70 tests. The current-source regression passed 89 tests. The archived deterministic runtime trace recorded `PASS`: budget pause with 2/12 batches complete, resume to 12/12 and confirmation of the resulting report revision. The Skill and Prompt experiments verified the rejection and provenance controls for the recorded cases. The detailed scope, owners and source references are in the [completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md).

The 27 November team confirmation accepts the documented prototype scope. The refreshed source is identified above, with its own current regression and offline-rerun records. The team retained the null Skill result, the blocked production activation and the single-PR pilot limits in the handoff. Report revision/upload, presentation rehearsal and official submission remain delivery activities. The report PDF and LaTeX source are intentionally not pushed.

## Completed Sprint Retrospective

Reporting date: 27 November 2026. The team retained version baselines, evidence checks, bounded execution and candidate evaluation before activation. The completed V5 record documents the lessons, supporting evidence, member responsibilities and delivery follow-up.

The main lessons were to package evaluation fixtures with the source, retain negative results, preserve test failures and maintenance warnings, and record contributions alongside centralized GitHub uploads. Tianyi Jiang maintained setup and fixture guidance. Jianyu Zhou and Siye Tu reconciled evaluation outcomes and provenance. Xinyu Zhang retained regression and isolation records. Jiayu Zhu prepared the user-flow demonstration. Jiexuan Shen integrated the work and consolidated source and process evidence.

The adopted delivery follow-up is presentation rehearsal, confirmation of official submission access and deadlines. The development completion record and delivery follow-up are dated to the team's specified reporting checkpoint.

## Current member completion record

The [V5 contribution table](Contribution-Traceability.md) links each member's completed V5 task to source/tests and confirmed actual hours: Siye Tu 8 h, Jianyu Zhou 6 h, Xinyu Zhang 4 h, Tianyi Jiang 6 h, Jiayu Zhu 7 h and Jiexuan Shen 5 h (36 V5 hours). All members total 36 h each across V1–V5. Technical reruns validate the product and are distinct from individual authorship evidence.

## Separate version records

- V4: [Review](V4-Review.md) and [Retrospective](V4-Retrospective.md).
