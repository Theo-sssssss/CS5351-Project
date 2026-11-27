# EvoAgent V3 Review — Sprint 2

Group 04. Team name: **group**.

- Global version: **V3**; course Sprint: **Sprint 2**.
- Sprint period: 12 October–8 November 2026.
- Related course Review / Retrospective: 6 November 2026 (course ceremony); V3 source followed on 7 November.
- Source upload: 7 November 2026.
- Record prepared: 28 November 2026, from retained sources and team-confirmed allocation.
- Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang.

## Increment goal and scope

**Bounded read-only tools and recoverable execution.** Read-only diff tools, bounded role decisions, execution budgets, checkpoints, cancellation and resume. V3 also protects Critic-validated findings from being dropped or replaced by synthesis. A backlog repair-policy/patch assignment is not, by itself, evidence that every proposed automatic-repair feature shipped.

## Completed work supported by the snapshot

| Work area | Retained implementation |
| --- | --- |
| Bounded repository tools | Registered operations read the already retrieved PR diff. Role permissions, schemas and observation sizes constrain access. |
| Execution limits | Program-controlled step, model-call, token and elapsed-time limits bound the role loop. |
| Recovery and cancellation | Completed node checkpoints are retained; compatible resume reuses them, while changed input fingerprints reject incompatible state. |
| Report integrity | Final synthesis preserves validated finding records. A report with no publishable findings does not assert that the code is defect-free. |

## Member allocation and actual effort

The following ownership and hours follow the team-confirmed backlogs and contribution table. Members handed outputs to Jiexuan Shen for integration and centralized GitHub submission; uploader identity is not sole-authorship evidence.

| Member | V3 actual hours | Assigned contribution |
| --- | ---: | --- |
| Jiexuan Shen | 10 | 13–15: verification gate and reporting |
| Jiayu Zhu | 12 | 16–18: UI/API, acceptance checks and demo |
| Siye Tu | 10 | 07–09: publication evidence, untrusted input and diff trimming |
| Tianyi Jiang | 10 | 01–03: runtime, budgets and checkpoint recovery |
| Jianyu Zhou | 14 | 04–06: tool contracts and read-only inspection |
| Xinyu Zhang | 12 | 10–12: assigned repair-policy/patch work packages; feature shipment requires separate evidence |
| Team total | **68** | Actual effort for this version |

Each member recorded 36 hours across the complete V1–V5 project. These version hours are not the reductions in estimated remaining work. Full allocation is in [Contribution Traceability](Contribution-Traceability.md).

## Verification evidence

| Behavior | Source test |
| --- | --- |
| Reject unauthorized or malformed tool actions | [test_permissions_and_argument_schema_are_enforced](https://github.com/Theo-sssssss/CS5351-Project/blob/aefe1f741cebf4e840b76726c84be5668a476c1d/src/sprint3/week1/EvoAgent_v3/tests/test_v3_runtime.py#L134) |
| Reuse completed checkpoint work | [test_completed_checkpoint_skips_model](https://github.com/Theo-sssssss/CS5351-Project/blob/aefe1f741cebf4e840b76726c84be5668a476c1d/src/sprint3/week1/EvoAgent_v3/tests/test_v3_runtime.py#L123) |
| Enforce role-step limits | [test_role_step_budget_is_hard_limit](https://github.com/Theo-sssssss/CS5351-Project/blob/aefe1f741cebf4e840b76726c84be5668a476c1d/src/sprint3/week1/EvoAgent_v3/tests/test_v3_runtime.py#L149) |
| Preserve validated findings through synthesis | [test_synthesis_cannot_drop_or_replace_approved_finding](https://github.com/Theo-sssssss/CS5351-Project/blob/aefe1f741cebf4e840b76726c84be5668a476c1d/src/sprint3/week1/EvoAgent_v3/tests/test_review_integrity.py#L17) |

The [archived V3 regression](../evidence/regression/EvoAgent_v3-tests.txt) records **54 passing tests**. [Run metadata](../evidence/regression/test-runs.json) dates the retrospective check to **21 November 2026**. This document introduces no new test execution or real-model measurement. Those later tests verify the recovered snapshot rather than dating its original Sprint acceptance.

## Review discussion and outcome

V3 was uploaded one day after the Sprint 2 Review and before the 8 November Sprint close. This document reviews the retained V3 increment as Sprint-end follow-up; it does not assert that the uploaded build was demonstrated or accepted at the 6 November meeting. Its role/tool and recovery contracts are supported by subsequent tests, not by calendar evidence.

**Recorded outcome:** The archived 54-test result verifies the recovered V3 test scope. No separate V3 Review date or version-specific formal sign-off was supplied, and a pre-upload demonstration on 6 November is not established. V3 remains within Sprint 2; the version folder name does not create a third course Sprint.

## References and next increment

- [Pinned V3 source](https://github.com/Theo-sssssss/CS5351-Project/tree/aefe1f741cebf4e840b76726c84be5668a476c1d/src/sprint3/week1/EvoAgent_v3)
- [Version backlog](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a111f24bff749a8dc1c26c9aa56bddf2b88/docs/Sprint_Backlog_V3.xlsx)
- [Course Sprint record](Sprint-2-Records.md)
- [V3 Retrospective](V3-Retrospective.md)
- [Repository and evaluation evidence](Evidence-Index.md)

Evaluate V4 bounded context, scoped feedback and declarative Skills without expanding tools to arbitrary repository modification. Keep compatible-input checks and report coverage observable. Any automatic-repair claim needs its own before/after and verification evidence.
