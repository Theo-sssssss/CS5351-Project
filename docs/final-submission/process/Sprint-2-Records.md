# EvoAgent Sprint 2 Records

Period: 12 October–8 November 2026, course Weeks 6–9.

Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou, and Xinyu Zhang.

Planning: 12 October 2026. Review and Retrospective: 6 November 2026. Dates supplied by the team.

Status: reconstructed Planning and Retrospective draft with an evidence-based technical Review. Actual decisions and formal acceptance are pending team confirmation.

The team confirmed all six members attended the meetings already held. The technical discussion below is reconstructed from version evidence. Formal acceptance and adopted actions remain unverified.

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

### Verification and acceptance scope

The handoff records retrospective regressions on 21 November with 33 tests passing for V2 and 54 for V3. Covered behaviors include collaboration stages, finding gates, execution limits, and recovery. These logs establish later snapshot checks rather than the dates of historical Sprint acceptance.

The evidence supports the controlled review workflow. It does not establish that more Agents improve real-world accuracy. A location gate verifies source correspondence, while semantic correctness still requires evaluation. Formal acceptance outcome: pending team confirmation.

### Carry-forward work

Add bounded risk-aware context selection, repository-scoped feedback memory, and declarative Skills. Evaluate feedback-driven candidates before allowing them to affect future reviews. Retain explicit failures and compare costs under the same input and budget.

## Sprint Retrospective

Date: 6 November 2026, the same date as the Sprint Review. The order and times of the two meetings have not been specified.

### What worked

Fixed role boundaries made intermediate results inspectable. Programmatic evidence checks provided repeatable rejection behavior. Checkpoints created a mechanism for recovering work without repeating all completed calls.

### Problems and lessons

Collaboration increases model calls and possible failure paths. Tool use and persistence introduce permission and state-consistency risks. Large diffs can exceed context or execution budgets. Raising the budget alone does not demonstrate a better review method.

### Proposed improvement actions

| Action | Proposed owner | Target | Completion criterion |
| --- | --- | --- | --- |
| Bound and explain context selection | Siye Tu | Sprint 3 | Selected context stays within configured limits and records its scope. |
| Add repository and tenant isolation tests for memory | Xinyu Zhang | Sprint 3 | Cross-scope recall is rejected and valid feedback remains retrievable. |
| Validate declarative Skill configuration and permissions | Jiexuan Shen | Sprint 3 | Invalid manifests and unauthorized tool access are rejected. |
| Extend budget and execution measurements | Jianyu Zhou | Sprint 3 | Comparisons record completion, failures, tokens, and elapsed time. |
| Exercise checkpoint reuse under interruption | Jiayu Zhu | Sprint 3 | Previously completed stages are not repeated on compatible resume. |
| Review tool schemas and bounded observations | Tianyi Jiang | Sprint 3 | Illegal arguments fail with traceable errors. |

Actual meeting decisions and action acceptance: pending team confirmation.
