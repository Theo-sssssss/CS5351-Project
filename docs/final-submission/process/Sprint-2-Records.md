# EvoAgent Sprint 2 Records

Group 04. Team name: **group**. Documentation updated on 28 November 2026. The ceremony dates below remain historical.

Period: 12 October–8 November 2026, course Weeks 6–9.

Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou, and Xinyu Zhang.

Planning: 12 October 2026. Review and Retrospective: 6 November 2026. Dates supplied by the team.

Status: finalized reconstructed Planning and Retrospective account with an evidence-based technical Review. Unrecorded historical decisions and formal acceptance are not established by the available evidence.

The team confirmed all six members attended the meetings already held. The technical discussion below is reconstructed from version evidence. Formal acceptance and adopted actions remain unverified.

## Weekly calendar evidence

| Course week | Scheduled date | Screenshot |
| --- | --- | --- |
| Week 06 | 2026-10-16 | [Calendar screenshot](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-06-2026-10-16.jpg) |
| Week 07 | 2026-10-23 | [Calendar screenshot](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-07-2026-10-23.jpg) |
| Week 08 | 2026-10-30 | [Calendar screenshot](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-08-2026-10-30.jpg) |
| Week 09 | 2026-11-06 | [Calendar screenshot](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/evidence/week-09-2026-11-06.jpg) |

These screenshots record scheduled entries. The team separately confirmed attendance; original meeting votes, live demonstrations and sign-offs are not reconstructed from calendar images.

## Sprint Planning

Date: 12 October 2026.

### Goal

Extend the single-call baseline into collaborative review whose evidence, tool authority, resource consumption, and recovery behavior can be inspected and tested.

### Selected work and acceptance criteria

| Work item | Related user story | Acceptance criteria |
| --- | --- | --- |
| Fixed multi-role review | US01, US08 | Lead, Security, Correctness/Reliability, Critic, and synthesis stages have identifiable execution records. |
| Diff evidence gate | US03, US08 | Findings must reference a valid added line and matching source evidence; duplicates are handled consistently. |
| Role-level usage reporting | US05 | Reports expose participating roles and aggregate model usage. |
| Read-only diff tools | US08, technical enabler | Only allowed tools and role permissions are accepted; arguments and result sizes are bounded. |
| Execution budgets | US06, technical enabler | Step, call, token, and time limits stop subsequent execution and produce an explicit state. |
| Checkpoint, cancellation, and resume | US05, US06, extended scope | Completed work can be reused after interruption, and incompatible diff checkpoints are rejected. |
| Integrity and failure tests | Foundation | Tests cover rejected evidence, unauthorized actions, malformed responses, budget limits, and recovery. |

### Design rationale and estimates

Safety and isolation are addressed through read-only tools, role permissions, schema validation, and diff evidence gates. Reliability and recovery are addressed through explicit state, execution budgets, and persistent checkpoints. These are two non-functional requirements with concrete architectural choices.

After V2, the team's estimated remaining development work was 132 hours; after V3, it was 72 hours. Compared with the preceding version milestones, the decreases were 54 and 60 hours. Treat them as estimate changes rather than actual labor or story points.

## Sprint Review

Date: 6 November 2026.

### Increment and repository evidence

V2 introduces fixed collaboration and evidence checks. V3 adds bounded read-only tools, runtime budgets, cancellation, and checkpoint recovery. Its integrity changes preserve Critic-validated findings during final summarization.

V3 was uploaded on 7 November, one day after the specified Review. It is included here as a Sprint-end follow-up within the 8 November Sprint close. The upload alone does not establish that V3 was demonstrated or accepted at the 6 November Review.

| Evidence | Repository reference |
| --- | --- |
| V2 backlog | [103fcce](https://github.com/Theo-sssssss/CS5351-Project/commit/103fccecd98c038b5112cd6ea0c41cad46808071), 18 October |
| V2 source | [f231554](https://github.com/Theo-sssssss/CS5351-Project/commit/f2315543fd577c573d1e629d9e39750107047a40), 18 October |
| V3 source | [aefe1f7](https://github.com/Theo-sssssss/CS5351-Project/commit/aefe1f741cebf4e840b76726c84be5668a476c1d), 7 November |

### Reconstructed technical discussion for 6 November

| Topic | What the available work showed | Verification focus and later work |
| --- | --- | --- |
| V2 role workflow | V2 used a shared report schema, a Lead plan, two specialist calls, a Critic pass and final synthesis. The user could inspect role traces and compare the baseline and collaborative modes. | For the same diff, compare completion, calls and findings. Retain failure outcomes. |
| Location and quotation checks | The gate screened invalid paths, non-added lines, mismatched code evidence and duplicate findings. A passing location check establishes correspondence to the source line. | Keep the report distinction between traceability and semantic correctness. |
| Service and delivery boundaries | The backlog assigns GitHub intake and persistence separately from dashboard controls and reporting. A completed review and success posting a comment are tracked independently. | Preserve that distinction in acceptance checks and capture explicit errors from each layer. |
| V3 Sprint-end follow-up | The 7 November upload followed the Review. It added bounded read-only context, limits and checkpoint handling. Later regressions recorded 33 V2 and 54 V3 passes. | Treat V3 as Sprint-end evidence. The retained record does not establish whether a pre-upload V3 build was shown at the Review. |
| Retrospective issue | Collaboration increases calls and the number of intermediate states. Limits and checkpoint reuse reduce repeated work after interruption. | In Sprint 3, check bounded context, scoped memory and reuse of completed work under interruption. |

These are evidence-based topics for the Review and Retrospective record. The 33 and 54 test counts are subsequent regression evidence. The retained record does not establish formal adoption at the original meeting; subsequent implementation is documented below.

### Verification and acceptance scope

The handoff records retrospective regressions on 21 November with 33 tests passing for V2 and 54 for V3. Covered behaviors include collaboration stages, finding gates, execution limits, and recovery. These logs establish later snapshot checks rather than the dates of historical Sprint acceptance.

The evidence supports the controlled review workflow. It does not establish that more Agents improve real-world accuracy. A location gate verifies source correspondence, while semantic correctness still requires evaluation. Historical formal acceptance outcome: not established by the retained evidence.

### Carry-forward work

Add bounded risk-aware context selection, repository-scoped feedback memory, and declarative Skills. Evaluate feedback-driven candidates before allowing them to affect future reviews. Retain explicit failures and compare costs under the same input and budget.

## Sprint Retrospective

Date: 6 November 2026, the same date as the Sprint Review. The order and times of the two meetings have not been specified.

### What worked

Fixed role boundaries made intermediate results inspectable. Programmatic evidence checks provided repeatable rejection behavior. Checkpoints created a mechanism for recovering work without repeating all completed calls.

### Problems and lessons

Collaboration increases model calls and possible failure paths. Tool use and persistence introduce permission and state-consistency risks. Large diffs can exceed context or execution budgets. Raising the budget alone does not demonstrate a better review method.

### Retrospective lessons and subsequent implementation

The following outcomes describe later completed increments. The named contributors follow the team-confirmed later assignments; they do not assert unrecorded votes or sign-offs at the 6 November meeting.

| Lesson from collaboration and bounded execution | Later responsible contributors | Subsequent outcome and evidence |
| --- | --- | --- |
| Bound and explain review context. | Tianyi Jiang, V4 T01–T03 | V4 added risk ranking and bounded diff context; [V4 regression](../evidence/regression/EvoAgent_v4-after-tests.txt) records its maintained snapshot. |
| Scope repository feedback and verify tenant boundaries. | Jianyu Zhou and Xinyu Zhang, V4 memory and isolation assignments | Scoped memory and rejection tests are retained in the current source and current [89-test run](../evidence/release/latest-source-test-run.json). |
| Validate declarative Skills and permitted tools. | Siye Tu and Xinyu Zhang, V4 manifest and permission assignments | Manifests, role selection and permission boundaries are covered by the later Skill/runtime tests. |
| Preserve work under interruption and expose incomplete coverage. | Jiexuan Shen and Jiayu Zhu, runtime and user-flow integration | The current delivery exposes budget pause, checkpoint resume and revision-specific report confirmation. |
| Evaluate feedback-driven changes before production publication. | Jianyu Zhou, Siye Tu and Xinyu Zhang, V5 evaluation/candidate/gate assignments | The [current-source rerun](../evidence/evaluation/current-source-20261127/README.md) retains the null Skill gain and prompt provenance block. |

The original Sprint 2 formal acceptance decision and any pre-upload V3 demonstration remain unrecorded. V3's 7 November upload is Sprint-end follow-up, and later tests verify the recovered snapshots rather than dating acceptance to 6 November.

## Current delivery cross-reference

V1–V3 remain historical increment references. The refreshed V5 source is [e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5), with 89 current-source regression passes and separately reported offline metrics. The [completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md) and [V5 member contributions](Contribution-Traceability.md) document the final increment. The report remains local at the user's request.

## Separate version records

- V2: [Review](V2-Review.md) and [Retrospective](V2-Retrospective.md).
- V3: [Review](V3-Review.md) and [Retrospective](V3-Retrospective.md).
