# EvoAgent Sprint 3 Records

Period: 9–30 November 2026, course Weeks 10–13.

Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou, and Xinyu Zhang.

Planning: 9 November 2026. Review and Retrospective completion account: 27 November 2026, as specified by the team. The Sprint closes on 30 November.

Status at the team-specified 27 November reporting checkpoint: documented development scope completed and accepted against the archived verification evidence. The participants are listed above. This account incorporates team confirmation and source inspection. See the [completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md) for task-level evidence.

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

V4 and V5 are restored snapshots containing shared infrastructure. Attribute their intended increments using their `VERSION_SCOPE.md` files rather than treating every included module as newly developed in that version.

The team previously selected [src/final/EvoAgent on codex/evoagent-final-delivery](https://github.com/Theo-sssssss/CS5351-Project/tree/codex/evoagent-final-delivery/src/final/EvoAgent) as the final submission source. The inspected commit is `b9a63e3097635cc5d6f6bad14b82732da43dba02`. This was the selected baseline and does not relabel the snapshot as V6. The user-supplied 27 November refresh is now the current local source archive, with 99 files and 89 passing regression tests. Its identity is in `../evidence/release/current-delivery-update.json`; the source revision is `e48ee634b7f609a89f761adc8b7a516cb8fcba31` on `main`.

### Technical results

The handoff logs record 70 passing tests for the repaired V4 snapshot and 70 for V5. The current delivery source passed 89 tests. The original V4 regression produced five missing-fixture errors and one quotation-sensitive assertion failure. Retaining the before-and-after logs makes this maintenance work traceable. These archived logs remain unchanged. A separate 27 November check of the refreshed source ZIP passed 89 tests after extraction; see `../evidence/release/latest-source-test-run.json`.

The final snapshot adds batch coverage, budget pause and resume, report confirmation, and a workbench separating evaluation readiness from publication.

### Evaluation results

The 100-case controlled offline experiment reported F1 of 90.41% for both the full workflow and the workflow with an evolved Skill. It did not demonstrate a Skill improvement. A separate 130-case Prompt replay improved fixture validation and holdout F1 from 66.67% to 100%, while the production provenance gate blocked activation. Neither experiment establishes live PR accuracy.

A frozen public documentation PR was also reviewed using a real model. The batched engine completed in 27.415 seconds, used 9,262 recorded tokens, and covered one of one batches. The legacy engine exceeded its task execution budget after 45.876 seconds of client elapsed time. There was no independent ground truth, so this pilot establishes a recorded execution outcome rather than a comparative accuracy or general reliability result.

### Review verification and acceptance

The team confirmed completion of the allocated V5 work. V5 regression passed 70 tests. The current-source regression passed 89 tests. The archived deterministic runtime trace recorded `PASS`: budget pause with 2/12 batches complete, resume to 12/12 and confirmation of the resulting report revision. The Skill and Prompt experiments verified the rejection and provenance controls for the recorded cases. The detailed scope, owners and source references are in the [completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md).

The selected delivery snapshot `b9a63e3` was accepted for the documented prototype scope. The team retained the null Skill result, the blocked production activation and the single-PR pilot limits in the handoff. Presentation rehearsal, official submission remain delivery activities.

## Completed Sprint Retrospective

Reporting date: 27 November 2026. The team retained version baselines, evidence checks, bounded execution and candidate evaluation before activation. The completed V5 record documents the lessons, supporting evidence, member responsibilities and delivery follow-up.

The main lessons were to package evaluation fixtures with the source, retain negative results, preserve test failures and maintenance warnings, and record contributions alongside centralized GitHub uploads. Tianyi Jiang maintained setup and fixture guidance. Jianyu Zhou and Siye Tu reconciled evaluation outcomes and provenance. Xinyu Zhang retained regression and isolation records. Jiayu Zhu prepared the user-flow demonstration. Jiexuan Shen integrated the work and consolidated source and process evidence.

The adopted delivery follow-up is presentation rehearsal, confirmation of official submission access and deadlines. The development completion record and delivery follow-up are dated to the team's specified reporting checkpoint.

## Current-source offline rerun — 27 November 2026

A separate execution from the refreshed 99-file source archive reproduced the controlled fixture metrics: full-workflow aggregate precision/recall/F1 100.00% / 82.50% / 90.41%; held-out precision/recall/F1 100.00% / 62.50% / 76.92%. The evolved Skill gave zero matched holdout gain. The separate 130-case prompt replay also reproduced its metrics and production activation block. These no-LLM results are in `../evidence/evaluation/current-source-20261127/`. The historical increment records and single real-PR pilot remain attributed to their original inputs.

## Current uploaded-source identity

The verified refreshed source is [e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5). The report PDF and LaTeX source are intentionally withheld from this upload. Historical increment links above retain their historical scope.
