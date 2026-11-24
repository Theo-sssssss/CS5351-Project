# Contribution traceability

The sources below record backlog ownership. A planned owner is evidence of assigned responsibility. Completed work and actual hours require corroboration from commits, reviews, acceptance records or the person's contribution statement. V1 rows carrying only a letter code are left unattributed where the mapping is unclear. The V3 repair packages are listed as assigned scope. Their inclusion here makes no claim that each planned feature shipped.

| Member | V1 named tasks | V2 | V3 | V4 | Proposed V5 and final delivery ownership |
| --- | --- | --- | --- | --- | --- |
| Tianyi Jiang | PR metadata and diff retrieval (SB-05) | QA and Scrum (SB13--SB15) | Runtime, budgets, and checkpoint recovery (01--03) | Risk ranking and bounded diff context (T01--T03) | Maintain release reproducibility. Verify clean setup, configured dependencies and matching source hashes. |
| Jianyu Zhou | Runtime artifact handling and baseline model call (SB-03, SB-08) | Review integrity (SB06, SB09, SB12) | Tool contracts and read-only inspection (04--06) | Scoped memory, recall and expiry (T04--T06) | Own evaluation reproducibility. Verify offline splits, model settings, pilot outcomes and limits on claims. |
| Jiayu Zhu | PR URL validation (SB-04) | Platform integration (SB07--SB08) | UI, API, acceptance tests and demo (16--18) | Adaptive integration and release handoff (T16--T18) | Own final user-flow acceptance. Walk submission, report coverage, resume and confirmation. |
| Siye Tu | Local HTTP service and dashboard hosting (SB-02) | Model integration (SB02, SB04) | Publication evidence, untrusted input, and diff trimming (07--09) | Skill manifests and role selection (T07--T09) | Own evolution workbench acceptance. Check candidate provenance, gate outcomes and release identity. |
| Xinyu Zhang | Configuration and webhook deduplication (SB-01, SB-07) | Frontend and comparison entry (SB10--SB11) | Repair-policy and patch work packages (10--12) | Tenant isolation and tool permissions (T10--T12) | Own packaged regression and access-control verification. Preserve before/after logs and rejected actions. |
| Jiexuan Shen | Asynchronous task lifecycle (SB-06) | Workflow design (SB01, SB03, SB05) | Verification gate and reporting (13--15) | Task budgets, checkpoints and cancellation (T13--T15) | Own final runtime and process evidence. Reconcile task states, incomplete coverage and Sprint acceptance records. |

The six final packages target comparable scope. These proposed responsibilities cover identifiable outputs and do not retroactively allocate authorship. Each member should add links to their completed work, the confirmed hours if available, a biography and a personal reflection.

## Work performed at project level and individual responsibility

The repository and tests establish project-level outcomes. The bullets pair those outcomes with the corresponding named assignments. The V5 and final work below specifies an owner and a verifiable output for this handoff. Each member should confirm implementation authorship and individual completion separately.

- **Tianyi Jiang.** V1 assignment covered obtaining PR metadata and the diff. V2 assigned QA, smoke testing and Scrum tracking. V3 assigned runtime transitions, budgets and recovery. V4 assigned risk ranking, context selection and boundary tests. The final reproducibility package should match the selected source ZIP and manifest and retain the setup and regression instructions.
- **Jianyu Zhou.** V1 assignment covered excluded local artifacts and the fixed-prompt review call. V2 covered the diff gate and reporting safeguards. V3 assigned tool contracts and read-only diff inspection. V4 assigned repository feedback storage, bounded recall and expiration. The final evaluation package should record splits, provenance, the negative Skill result, the prompt replay and the paired public PR run.
- **Jiayu Zhu.** V1 assignment covered validating submitted PR URLs. V2 covered GitHub integration and task storage. V3 covered UI and API controls, acceptance tests and the demo. V4 covered integration of context, memory and skills. The final walkthrough should record submission, partial coverage, resume, complete coverage and report confirmation.
- **Siye Tu.** V1 assignment covered serving the dashboard and starting the local service. V2 covered the model client and specialist integration. V3 covered finding evidence, external input boundaries and diff trimming. V4 covered skill manifests and role selection. The final evolution package should document the candidate evaluation, provenance decision and distinction between eligibility and activation.
- **Xinyu Zhang.** V1 assignment covered environment configuration and webhook deduplication. V2 covered the dashboard and comparison control. V3 records the assigned policy and patch work packages. V4 covered tenant and repository isolation and associated regression checks. The final regression package should retain the V4 before and after results and the packaged-source 84-test evidence.
- **Jiexuan Shen.** V1 assignment covered asynchronous task state. V2 covered the Lead, specialists, Critic and synthesis workflow design. V3 covered verification and reporting. V4 covered budget, cancellation and resume handling. The final process evidence should link the runtime trace, partial coverage and release acceptance record while preserving any unresolved outcome.

## Repository workbooks

- [V1](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/EvoAgent_V1_Sprint_Backlog.xlsx)
- [V2](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/EvoAgent-V2-Sprint-Backlog.xlsx)
- [V3](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/Sprint_Backlog_V3.xlsx)
- [V4](https://github.com/Theo-sssssss/CS5351-Project/blob/faf93a1/docs/Sprint_Backlog_V4.xlsx)
