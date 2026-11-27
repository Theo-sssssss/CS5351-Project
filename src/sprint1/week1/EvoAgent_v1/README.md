# EvoAgent V1 — Single-Call PR Review Baseline

V1 is the Sprint 1 increment. It retrieves a GitHub pull-request diff, makes one OpenAI-compatible Chat Completions request, normalizes the returned JSON and stores a structured report in SQLite. It does not implement Lead/Worker/Critic collaboration, autonomous tools, memory, Skills or checkpoint resume.

```text
PR URL or signed webhook -> GitHub diff -> one model call
-> JSON normalization -> saved task/report -> local dashboard
```

## Start

Python 3.10+ is required. This version uses the Python standard library.

```bash
cd src/sprint1/week1/EvoAgent_v1
cp -n .env.example .env
# Configure the local model and GitHub settings.
./start.sh
```

Open `http://127.0.0.1:8082/`. Preserve an existing `.env` rather than replacing its configuration.

## Configuration

| Setting | Purpose |
| --- | --- |
| `PROMPT_REVIEW_GITHUB_TOKEN` | Read PR metadata/diffs; required for private repositories and permitted external actions. |
| `PROMPT_REVIEW_GITHUB_WEBHOOK_SECRET` | Verify GitHub webhook signatures. |
| `PROMPT_REVIEW_LLM_BASE_URL` | OpenAI-compatible provider endpoint. |
| `PROMPT_REVIEW_LLM_API_KEY` | Your provider key. |
| `PROMPT_REVIEW_LLM_MODEL` | Model identifier. |
| `PROMPT_REVIEW_AUTO_POST_REVIEW` | Optional summary posting; false by default. |

## API and GitHub integration

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Configuration health. |
| POST | `/api/reviews/from-pr` | Create a review from a PR URL. |
| POST | `/api/github/connect` | Configure a repository webhook when the token permits it. |
| GET | `/api/tasks` | List tasks. |
| GET | `/api/tasks/{id}` | Inspect task state and report. |
| POST | `/webhooks/github` | Receive supported signed PR events. |

The webhook handles `opened`, `reopened` and `synchronize`, and verifies `X-Hub-Signature-256`. External webhook delivery requires a reachable HTTPS endpoint. Manual PR submission can be used without exposing the dashboard. Optional posting requires the corresponding repository permissions.

## Verification and version records

```bash
python3 -m unittest discover -s tests -v
```

The archived V1 regression records two passing parsing/normalization tests, not a real-model accuracy score or historical live-integration sign-off. See [V1 Review](../../../../docs/final-submission/process/V1-Review.md) and [V1 Retrospective](../../../../docs/final-submission/process/V1-Retrospective.md).

PR diffs are sent to the configured provider. Keep real `.env`, tokens, databases and caches out of shared source. The service listens locally by default; expose only the required integration endpoint when configuring public webhooks.
