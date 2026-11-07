# EvoAgent V3

## Review-integrity improvements (2026-10-29)

- Final synthesis retains Critic-validated finding records and uses the synthesis model only for a summary, preventing paths, code evidence, and explanations from being rewritten or lost.
- The publication gate requires complete single-line code evidence, ignoring whitespace-only differences, and a non-empty explanation. An explanation containing a code fragment is not treated as valid evidence.
- When no candidate passes the gate, the report explicitly states that no publishable finding exists; this does not mean the code is defect-free. The raw summary remains in `model_summary`.
- Each LLM call runs in a separate worker process. `TIMEOUT_SECONDS` limits the complete call; on timeout, the local request process is terminated and usage is marked unknown. Whether a provider stops billing is provider-specific.
- Prompts require a stated trigger, verification against actual control flow, and no definite claim about unseen callers, databases, or validators. This improves evidence discipline but does not guarantee semantic correctness.

V3 is the third incremental reproduction after V1 single-prompt review and V2 fixed multi-role collaboration. It retains both earlier versions and adds read-only Repository Tools, a bounded decision loop, shared budgets, checkpoints, cancellation, and resume for the four review roles.

```text
Lead Agent (planning + read-only tools)
  ├─ Security Agent (parallel + read-only tools)
  └─ Correctness/Reliability Agent (parallel + read-only tools)
                         ↓
                 Critic Agent (review + tools)
                         ↓
                  Lead fixed final synthesis
                         ↓
                  Diff evidence gate
```

## Comparable versions

| Capability | V1 baseline | V2 collaborative | V3 agentic |
| --- | --- | --- | --- |
| Model calls | Fixed 1 | Fixed 5 | Up to 4 steps per role and 18 total calls |
| Role split | None | Lead, two Workers, Critic | Same topology, but roles may choose tools |
| Repository Tools | No | No | Four read-only Diff tools |
| Checkpoint / Resume | No | No | Yes |
| Cancellation | No | No | Yes |
| Step, token, and time budgets | No | Recorded only | Hard limits |
| Final evidence gate | Yes | Yes | Yes |

`agentic` is not an unbounded autonomous loop. Tool allowlists, role permissions, parameter formats, step limits, model-call limits, token limits, and time limits are program-controlled. The model cannot run a shell, modify a repository, or access arbitrary files.

## Start

Python 3.10+ is required. No third-party package is required.

```bash
cd ~/Desktop/EvoAgent_v3
cp .env.example .env
# Edit .env and enter the model endpoint, API key, and model name.
./start.sh
```

Open <http://127.0.0.1:8084>.

The model provider must support OpenAI Chat Completions. Prefer a complete `EVOAGENT_V3_LLM_CHAT_COMPLETIONS_URL`; when only a base URL is set, the program appends `/chat/completions`. A GitHub token is optional for public PRs but required for private repositories and comment delivery.

## V3 Repository Tools

- `list_changed_files`: list files and added-line counts from the Diff.
- `get_added_lines`: read a bounded set of added lines from one file.
- `search_added_code`: perform case-insensitive literal search across added code.
- `get_diff_context`: read bounded context around one real added line.

Every tool reads only the PR Diff already retrieved for the task. The Lead role does not have `get_diff_context`. Tool name, role permission, and parameter schema are validated again before execution.

## Budgets and recovery

Default budgets are defined in `.env.example`: up to four steps per role, 18 model calls, 30,000 tokens, and 240 seconds per task. Exceeding any limit fails explicitly and never silently expands the budget.

Each completed Agent node saves a checkpoint, and tool observations are stored in SQLite. When the service stops unexpectedly, active `agentic` tasks become `PAUSED` and can be resumed through the UI or API. Before resuming, the service retrieves the PR Diff again; a changed Diff fingerprint rejects the old checkpoint and requires a new task.

Cancellation takes effect before the next model call. Completed checkpoints do not execute again, and already consumed model calls and tokens still count against the resumed task budget.

## Web UI and API

The UI can run individual V1, V2, or V3 reviews, or create all three tasks for the same PR to compare finding quality and cost.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Configuration, TLS, and Agent budget |
| `GET` | `/api/tasks` | Recent tasks |
| `GET` | `/api/tasks/{id}` | Report, role traces, tool events, and checkpoints |
| `POST` | `/api/reviews/from-pr` | Create a baseline, collaborative, or agentic review |
| `POST` | `/api/reviews/compare` | Create V1/V2/V3 comparison tasks |
| `POST` | `/api/tasks/{id}/cancel` | Request cancellation of a running task |
| `POST` | `/api/tasks/{id}/resume` | Resume an Agentic checkpoint |
| `POST` | `/webhooks/github` | Signed GitHub PR webhook; runs agentic mode by default |

```bash
curl -X POST http://127.0.0.1:8084/api/reviews/from-pr \
  -H 'Content-Type: application/json' \
  -d '{"pull_request_url":"https://github.com/owner/repo/pull/42","mode":"agentic"}'
```

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py evoagent_v3/*.py
node --check static/app.js
sh -n start.sh
```

The automated tests use a local fake LLM and do not contact a real GitHub API or model service.

## Boundaries

- A finding is published only when its path, added line, and evidence can be verified in the Diff.
- Tools see added Diff lines, not complete repository semantics; reports must preserve that evidence boundary.
- Oversized Diffs fail explicitly rather than being silently truncated.
- Model-review success and GitHub-comment delivery are recorded separately; delivery failure does not remove a report.
- `.env`, databases, and caches are ignored. Do not include secrets, databases, or runtime caches in shared packages.
- The service listens on `127.0.0.1` by default. Expose only the webhook path through a reverse proxy when receiving public webhooks.
- PR Diffs are sent to the configured model service. Review only repositories that the service is authorized to process.

## Recommended next evaluation

Run the same PR set with V1, V2, and V3 and record true-defect coverage, false-positive rate, model calls, tokens, and latency. Add full-repository retrieval, long-term memory, auto-fix, or more complex orchestration only when tool use shows a stable quality benefit.
