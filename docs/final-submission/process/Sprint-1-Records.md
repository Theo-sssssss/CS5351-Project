# EvoAgent Sprint 1 Records

Period: 7 September–4 October 2026, course Weeks 2–5.

Participants: Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou, and Xinyu Zhang.

Planning: 7 September 2026. Review and Retrospective: 2 October 2026. Dates supplied by the team.

Status: finalized reconstructed Planning and Retrospective account with an evidence-based technical Review. Unrecorded historical decisions and formal acceptance are not established by the available evidence.

The team confirmed all six members attended the meetings already held. The technical discussion below is reconstructed from version evidence. Formal acceptance and adopted actions remain unverified.

## Sprint Planning

Date: 7 September 2026.

### Goal

Deliver a working PR review baseline that accepts a GitHub pull request, retrieves its diff, performs one LLM review, stores the result, and displays a structured report.

### Selected work and acceptance criteria

| Work item | Related user story | Acceptance criteria |
| --- | --- | --- |
| Project configuration | Foundation | The service starts with documented configuration, a credential-free example environment file, and excluded local secrets and databases. |
| Manual PR submission | US01 | A valid PR URL creates a task; malformed input returns a clear error. |
| GitHub webhook handling | US01 | Supported pull-request events create tasks; invalid signatures and duplicate deliveries are handled explicitly. |
| Single-call review | US01 | The system fetches the PR diff and invokes the configured compatible LLM endpoint. |
| Structured report | US03 | Findings contain severity, path, line, evidence, explanation, suggested fix, and suggested test. |
| Task dashboard | US05, US06 | Users can inspect saved tasks, their current states, completed reports, and failures. |
| Optional summary comment | US04, partial scope | Posting can be enabled for a PR summary comment. V1 does not establish update-without-duplicates behavior for repeated report posting. |
| Basic tests and usage documentation | Foundation | JSON parsing and report normalization have tests, and setup instructions are available. |

### Estimate and dependencies

The initial project estimate was 216 hours of remaining development work. After V1, the team estimated 186 hours remaining. This is a 30-hour reduction in the estimate, not a measured timesheet total.

GitHub access, a valid PR, and a configured model endpoint are dependencies for live acceptance. Preserve the single-call version as a baseline for later collaboration experiments.

## Sprint Review

Date: 2 October 2026.

### Increment and repository evidence

V1 implements the submission-to-report workflow, SQLite task storage, a minimal web interface, and optional PR summary posting. Core, UI, test, and environment-template commits were uploaded on 13 September. The source was restored and its backlog was added on 22 September.

| Evidence | Repository reference |
| --- | --- |
| Prototype core | [5f88441](https://github.com/Theo-sssssss/CS5351-Project/commit/5f884417baa71975b898eeef8a469d126815b829) |
| Web interface | [9e00d8e](https://github.com/Theo-sssssss/CS5351-Project/commit/9e00d8e9e06a2c85d0591e3ae4a79de0a8c07520) |
| Basic tests | [eca700e](https://github.com/Theo-sssssss/CS5351-Project/commit/eca700e75d462b26525182612f267cc92c6b02a0) |
| Restored V1 source | [258b304](https://github.com/Theo-sssssss/CS5351-Project/commit/258b304f041af6457af73f247838c84aef9e013d) |
| V1 backlog | [d0a3b98](https://github.com/Theo-sssssss/CS5351-Project/commit/d0a3b98b9112ad6ef5f383a3381a7f93c1692850) |

### Reconstructed technical discussion for 2 October

| Topic | What the available work showed | Follow-up to confirm |
| --- | --- | --- |
| Intake and configuration | V1 established a local service and dashboard. The backlog separated environment configuration, URL validation, PR metadata and diff retrieval. Untracked credentials and database files were part of the setup boundary. | Verify a valid URL and an invalid URL against the same local release and record the observed task responses. |
| One-pass review | A submitted change flowed into a background task, one configured model call and a structured report. The task lifecycle and HTTP status were visible independently of the report. | Preserve V1 as the baseline and retain a frozen diff for the next comparison. |
| What counts as a valid finding | Report fields made results inspectable. The two later V1 tests cover parsing and normalization. They do not resolve whether a model's claim corresponds to a real issue on GitHub. | Introduce programmatic path and added-line evidence checks and separate them from assessment of correctness. |
| Scope for the next increment | One model response provided limited visibility into why a finding was produced. The next version introduced a Lead, specialists and Critic with individual execution records. | Use the named V2 workflow, integration and QA assignments in the contribution record. |

The October discussion is reconstructed from the V1 repository and backlog. The two-test result is retrospective. The contemporaneous live run and individual approval remain unrecorded.

### Verification and acceptance scope

The handoff archive records two V1 tests passing in a retrospective regression on 21 November. This supports the archived snapshot's tested parsing behavior; it does not date Sprint 1 acceptance or prove live GitHub and LLM integration at that time.

The baseline meets the implemented workflow scope. The team should record a live PR, configuration, expected result, observed result, and reviewer before signing off end-to-end acceptance. Historical formal acceptance outcome: not established by the retained evidence.

### Carry-forward work

Introduce independent specialist review and Critic verification, validate finding locations against parsed diff lines, and retain role-level execution and usage records. Keep summary-comment upsert and active completion notifications separate from the V1 feature claim.

## Sprint Retrospective

Date: 2 October 2026, the same date as the Sprint Review. The order and times of the two meetings have not been specified.

### What worked

A small executable baseline made the interfaces between PR input, model output, persistence, and reporting concrete. Preserving V1 enables later versions to be compared against a stable implementation.

### Problems and lessons

One model response has no independent challenge step. The initial tests cover parsing rather than review quality or the complete live workflow. Structured output alone cannot establish that a reported defect is valid.

### Proposed improvement actions

| Action | Proposed owner | Target | Completion criterion |
| --- | --- | --- | --- |
| Add Lead, specialist Workers, Critic, and final synthesis | Siye Tu | Sprint 2 | Role stages and their outputs are traceable. |
| Add diff-location and evidence rejection tests | Xinyu Zhang | Sprint 2 | Unknown paths, non-added lines, and mismatched quotations are rejected. |
| Record role-level calls, tokens, and states | Jiexuan Shen | Sprint 2 | A report can be traced to all participating stages. |
| Retain a reproducible baseline fixture and configuration | Jianyu Zhou | Sprint 2 | A frozen diff can be reused for a documented comparison. |

Historical meeting decisions and action acceptance: not established by the retained evidence.
