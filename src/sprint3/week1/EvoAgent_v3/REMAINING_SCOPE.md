# EvoAgent V3: Controlled Agent Review and Safe-Fix Loop

## Version goal

Build on V1's single-prompt review and V2's fixed multi-role collaboration to deliver an agentic review runtime that is resumable, auditable, budget-bounded, and unable to exceed its authority. High-confidence findings should also enter a restricted automated-fix and verification loop.

This document assigns the capabilities still missing after V1 and V2 to V3. Existing partial implementations must be completed and verified rather than duplicated.

## Required V3 scope

### 1. Bounded agent runtime

- A state machine for Lead, Security, Correctness/Reliability, and Critic roles, followed by a fixed final synthesis.
- Per-role step limits plus task-level limits for model calls, tokens, and elapsed time.
- Cancellation, explicit failure states, persistent checkpoints, PAUSED state after restart, and safe resume.
- Persisted role-input summaries, tool observations, model usage, and state transitions for every step.

Acceptance: exceeding any budget, a cancellation request, or a restart stops later model calls. Resume must not rerun completed steps and must reject an old checkpoint when the PR Diff fingerprint changes.

### 2. Read-only repository tools

- Read only the current PR Diff: changed files, added lines, bounded context, and literal search.
- Tool allowlist, role-permission matrix, parameter schema validation, result-size limits, and structured observations.
- No shell access, arbitrary file paths, expanded network access, repository writes, or GitHub writes.

Acceptance: invalid tools, unauthorized roles, invalid line numbers, and oversized parameters are rejected and audited. A model cannot use a tool to change code or expand its data boundary.

### 3. Diff evidence and input safety

- Preserve V1/V2 validation of path, added line, and complete code evidence.
- Mark PR text, source comments, and tool output as untrusted input so they cannot override system instructions.
- Provide deterministic trimming and summaries for large Diffs while retaining the complete Diff for read-only verification.

Acceptance: a finding without a valid path, line, or evidence cannot be published. Context trimming must not let fabricated evidence pass the gate.

### 4. Safe auto-fix and Draft PRs

- Support only deterministic, allowlisted fixes, such as unsafe debug output, `shell=True`, or hard-coded Python credentials.
- Generate patches with AST/CST or an equivalent structured mechanism; the model cannot write arbitrary code.
- Apply a patch in an isolated workspace, create a separate `evoagent/fix-pr-*` branch and Draft PR, and never merge the source branch directly.
- Link the original finding, patch, validation result, branch, and Draft PR in the report.

Acceptance: a finding outside the allowlist produces advice only. A failed patch application or verification must never create a Draft PR.

### 5. Repair-verification gate

- Run configured compilation, syntax, and repository tests before and after a repair.
- Persist commands, exit codes, bounded logs, and before/after results. Timeouts, failures, and unknown states must be explicit.
- Permit the repair branch only when every required gate succeeds.

Acceptance: failed tests, timeouts, or missing verification configuration block publication and do not overwrite the original review report.

### 6. API, user interface, and tests

- Expose V1/V2/V3 comparison tasks, cancellation, resume, repair requests, and repair status.
- Add unit and end-to-end coverage for the runtime, tool permissions, budgets, checkpoints, cancellation, Diff fingerprints, patches, and verification gates.
- Report task state, model calls, tokens, elapsed time, tool calls, accepted/rejected findings, and repair result through common metrics.

## Explicit V3 exclusions

- Long-term cross-task memory, risk-adaptive context, and dynamic Skills.
- Skill or prompt self-evolution, replay evaluation, and automatic activation.
- PostgreSQL, Redis queues, leases, dead-letter queues, and production multi-tenant governance.
- Login, RBAC, tenant/repository authorization, rollout controls, OpenTelemetry, and alerting.

All excluded capabilities belong to V4.

## Definition of done for V3

1. V1 and V2 regression behavior passes; a V3 agentic task can be created, cancelled, paused, and safely resumed.
2. All four read-only tools and their permission and parameter boundaries have automated tests.
3. Repairs create only verified Draft PRs and never merge code directly.
4. The demo includes a successful review, a budget or cancellation event, a resume, a rejected patch, and a successful Draft PR.
