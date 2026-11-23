# EvoAgent Sprint 3 Records

Period: 9–30 November 2026, course Weeks 10–13.

Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou, and Xinyu Zhang.

Planning: 9 November 2026. Review and Retrospective: scheduled for 27 November 2026, as explicitly specified by the team. The Sprint closes on 30 November.

Status as of 23 November 2026: Planning reconstructed from completed scope; Review is interim; Retrospective is an agenda with proposed actions. The scheduled Review and Retrospective have not yet taken place.

The team confirmed attendance by all six members at meetings already held, including Sprint 3 Planning. The 27 November Review and Retrospective are still scheduled. Attendance and decisions for those future events remain open.

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

The team specifies development from Week 2 through Week 12, with 30 hours remaining after V4 and zero after V5. The Week 12 discussion and Sprint 3 Review are scheduled for 27 November. The zero-hour endpoint covers the team-reported development scope; final report completion, rehearsal, and submission are still tracked as delivery actions. Individual milestone completion days are not inferred from upload dates.

## Interim Sprint Review

Scheduled date: 27 November 2026. The following technical findings are prepared for that meeting and are not its final minutes.

### Repository increments

| Snapshot | Uploaded date in GMT+8 | Repository evidence |
| --- | --- | --- |
| Restored V4 adaptive review | 21 November 2026 | [7a866fa](https://github.com/Theo-sssssss/CS5351-Project/commit/7a866faddaca3d715b987a1325bf7f2a7772ca5d) on `main` |
| Final-delivery integration snapshot | 21 November 2026 | [b9a63e3](https://github.com/Theo-sssssss/CS5351-Project/commit/b9a63e3097635cc5d6f6bad14b82732da43dba02) on `codex/evoagent-final-delivery` |
| Restored V5 controlled evolution | 23 November 2026 | [faf93a1](https://github.com/Theo-sssssss/CS5351-Project/commit/faf93a111f24bff749a8dc1c26c9aa56bddf2b88) on `main` |

V4 and V5 are restored snapshots containing shared infrastructure. Attribute their intended increments using their `VERSION_SCOPE.md` files rather than treating every included module as newly developed in that version.

The team has selected [src/final/EvoAgent on codex/evoagent-final-delivery](https://github.com/Theo-sssssss/CS5351-Project/tree/codex/evoagent-final-delivery/src/final/EvoAgent) as the final submission source. The inspected commit is `b9a63e3097635cc5d6f6bad14b82732da43dba02`. This choice resolves the submission branch; it does not relabel the snapshot as V6 or change the observed upload chronology. Align the report, video, and source archive with this selected source.

### Technical results

The handoff logs record 70 passing tests for the repaired V4 snapshot, 70 for V5, and 84 for the packaged final source. The original V4 regression produced five missing-fixture errors and one quotation-sensitive assertion failure. Retaining the before-and-after logs makes this maintenance work traceable. These archived logs have not been replaced with a new test run in preparing these records.

The final snapshot adds batch coverage, budget pause and resume, report confirmation, and a workbench separating evaluation readiness from publication.

### Evaluation results

The 100-case controlled offline experiment reported F1 of 90.41% for both the full workflow and the workflow with an evolved Skill. It did not demonstrate a Skill improvement. A separate 130-case Prompt replay improved fixture validation and holdout F1 from 66.67% to 100%, while the production provenance gate blocked activation. Neither experiment establishes live PR accuracy.

A frozen public documentation PR was also reviewed using a real model. The batched engine completed in 27.415 seconds, used 9,262 recorded tokens, and covered one of one batches. The legacy engine exceeded its task execution budget after 45.876 seconds of client elapsed time. There was no independent ground truth, so this pilot establishes a recorded execution outcome rather than a comparative accuracy or general reliability result.

### Proposed acceptance position

The available snapshots support review of the implemented development scope. The submission source is confirmed as the delivery-branch snapshot. At the 27 November Review, record the team's acceptance, the selected release's reproducibility result, remaining delivery work, and any exceptions. Track final delivery actions through the 30 November Sprint close. The final Review outcome remains pending until the meeting takes place.

## Sprint Retrospective Agenda

Scheduled date: 27 November 2026, the same date as the Sprint Review. The order and times of the two meetings have not been specified.

### Practices worth retaining

Retain version baselines, independent evidence gates, bounded execution, and candidate evaluation before publication. Preserve negative evaluation outcomes and maintenance failures alongside successful results.

### Issues to discuss

The original version-to-Sprint grouping differs from observed upload timing. Restored snapshots mix shared infrastructure with the intended version increments. Historical ceremony records and actual contribution records remain incomplete. Evaluation fixtures and one live PR provide different kinds of evidence and must remain clearly identified.

### Proposed closing actions

| Action | Proposed owner | Target | Completion criterion |
| --- | --- | --- | --- |
| Align delivery artifacts with the confirmed submission source | Siye Tu | Before Sprint close | Report, source archive, and GitHub reference identify delivery-branch commit b9a63e3 or a later explicitly accepted revision. |
| Reproduce release tests with documented dependencies | Xinyu Zhang | Before Sprint close | A dated test log records environment, source identity, and result. |
| Review fixed datasets and evaluation claims | Jianyu Zhou | Before report submission | Model, dataset provenance, metrics, budgets, and limitations agree across deliverables. |
| Rehearse dashboard and recovery demonstration | Jiayu Zhu | Before presentation | The walkthrough is repeatable and fits the allotted presentation time. |
| Check configuration and reproducibility instructions | Tianyi Jiang | Before handoff | Another team member can follow the setup without undocumented steps. |
| Consolidate acceptance records and remaining-work snapshots | Jiexuan Shen | Before Sprint close | Team decisions, milestone estimates, and references are available in the process record. |
| Confirm actual contributions and personal reflections | All six members | Before report submission | Each member approves their contribution statement and reflection. |

Retrospective date: scheduled for 27 November 2026. Adopted actions and final acceptance will be recorded after the team discussion.
