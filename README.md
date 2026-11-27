# EvoAgent — CS5351 Group 04

Team name: **group**. EvoAgent is a pull-request review assistant with evidence-linked findings, controlled agent/tool execution, batch coverage and checkpoint recovery, repository feedback, and evaluated Skill or prompt updates.

## Current delivery

- [V5 refreshed source](src/sprint5/week1/EvoAgent_v5)
- [Presentation, demo and delivery records](docs/final-submission)
- [Completed V5 Review and Retrospective](docs/final-submission/process/V5-Sprint-Backlog-Review-Retrospective.md)
- [Run and verify](docs/final-submission/RUN-AND-VERIFY.md)
- [Current-source offline evaluation](docs/final-submission/evidence/evaluation/current-source-20261127/README.md)

The current source archive passed **89 regression tests** after extraction with Python 3.11.5. On the 100-case controlled synthetic fixture, the full workflow measured precision 100.00%, recall 82.50% and F1 90.41% across all cases; on the separate 20-case holdout, precision was 100.00%, recall 62.50% and F1 76.92%. The evolved Skill gave zero matched holdout gain. These offline runs used deterministic rules and simulated model clients, not a real LLM. The report separately describes the archived single-public-PR execution pilot and its limits.

## Team and process

Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang each recorded 36 hours (216 team hours). Three course Sprints covered five version increments. Individual allocation is documented in the backlogs and confirmed contribution statements; members handed work to Jiexuan Shen for integration and centralized GitHub uploads.

The two non-functional requirements are security/isolation and reliability/recoverability. Their architecture choices and tests are described in the report. Course requirements and the original backlog workbooks remain in `docs/`. Historical source increments remain in `src/` and Git history.

## Delivery status

The report remains local and is intentionally not pushed at the user's request. It includes the required content categories, burndown, contribution allocation, biographies and confirmed self-reflections. It uses IEEEtran and has approximately 10,700 body words after the specified exclusions. The rubric check records the remaining section-length differences. Presentation rehearsal and official course submission remain team delivery activities. Website translation was deferred at the user's request; video inspection was waived.

Real environment settings, credentials, application databases, dependency environments and caches are excluded. Configuration templates are supplied as `.env.example`.
