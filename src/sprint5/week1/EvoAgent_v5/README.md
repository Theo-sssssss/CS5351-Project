# EvoAgent V5 — Verified Integrated PR Review

V5 belongs to course Sprint 3. It converts scoped review feedback into versioned Skill candidates, replays them on fixed partitions and separates evaluation eligibility from publication/rollback. The refreshed delivery also integrates batch coverage, bounded model/tool execution, checkpoint resume, report revision confirmation and deterministic checks for removed Python guards. See [VERSION_SCOPE.md](https://github.com/Theo-sssssss/CS5351-Project/blob/main/src/sprint5/week1/EvoAgent_v5/VERSION_SCOPE.md) and [EVALUATION_RESULTS.md](https://github.com/Theo-sssssss/CS5351-Project/blob/main/src/sprint5/week1/EvoAgent_v5/EVALUATION_RESULTS.md).

## Batch review and the version workbench

- New tasks split textual changes into bounded batches while retaining original changed-line locations and coverage state.
- Asynchronous tasks expose completed/outstanding work. A token-budget pause can be resumed with `POST /v1/tasks/{id}/resume` and `additional_tokens`; completed batches and role checkpoints are reused. Initial allowance is configured with `EVOAGENT_REVIEW_TASK_TOKEN_BUDGET`.
- A complete textual report can be confirmed with `POST /v1/tasks/{id}/accept` and the returned `report_revision`. Confirmation, GitHub posting, per-finding feedback and repair publication are distinct actions.
- Prompt/Skill candidates can be replayed and inspected before eligible publication through `/v1/versions/{prompt|skill}/{name}/{version}/publish`. Supported eligible versions can be used for controlled rollout/rollback. Prompt administration and tenant-scoped Skill rules remain explicit access boundaries.
- `EVOAGENT_REVIEW_BATCHING_ENABLED=false` selects the legacy path for new tasks. Existing tasks keep their creation-time engine. `scripts/compare_review_engines.py` compares paths under declared inputs/settings; unknown legacy coverage is not filled with a guessed value.

## Recorded verification

The current-source regression records 89 passing tests. The frozen 100-case controlled comparison measured full-workflow aggregate P/R/F1 of 100.00% / 82.50% / 90.41%; the separate 20-case holdout measured 100.00% / 62.50% / 76.92%. The evolved Skill gave zero matched holdout gain. These deterministic/simulated fixture runs do not invoke a real LLM. The separate prompt fixture improved its scores but did not pass production provenance. Complete outputs and source identities are under `docs/final-submission/evidence/` at the repository root.

The completed [V5 Review and Retrospective](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/final-submission/process/V5-Sprint-Backlog-Review-Retrospective.md) and [contribution table](https://github.com/Theo-sssssss/CS5351-Project/blob/main/docs/final-submission/process/Contribution-Traceability.md) document scope and ownership. README/local-run translation is a documentation change; executable implementation files are unchanged.

## Local setup

Python 3.11 is recommended. For the current V5 delivery:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
```

On Windows PowerShell, use `py -3.11 -m venv .venv` and `.\.venv\Scripts\python.exe`. Copy the example only when no real `.env` exists. The basic local workflow uses SQLite; PostgreSQL and Redis are not required for a first local run.

Configure a valid model before submitting a model-backed review. An OpenAI-compatible provider uses:

```dotenv
EVOAGENT_LLM_PROVIDER=custom
EVOAGENT_LLM_BASE_URL=https://your-provider.example/v1
EVOAGENT_LLM_API_KEY=<your-api-key>
EVOAGENT_LLM_MODEL=<your-model>
```

Provider presets also support `deepseek` with `EVOAGENT_DEEPSEEK_API_KEY` and configured OpenRouter providers with `EVOAGENT_OPENROUTER_API_KEY`. Available models and provider terms are external settings; choose a currently supported model. Root `.env` or `evoagent/.env` settings are loaded, with process environment variables taking priority.

For authenticated use, set `EVOAGENT_AUTH_REQUIRED=true`, a random `EVOAGENT_AUTH_SECRET`, and `EVOAGENT_BOOTSTRAP_ADMIN_USERNAME` / `EVOAGENT_BOOTSTRAP_ADMIN_PASSWORD`. Use your own password of at least 10 characters. Bootstrap creates an absent user; it does not overwrite an existing user's password. Restart after changing configuration.

```bash
.venv/bin/python -m evoagent
```

Open `http://127.0.0.1:8080/`. The service can start without a model, but health/startup alone is not a successful live review. API authentication uses `POST /v1/auth/login` and the returned Bearer token when authentication is enabled.

## GitHub intake and result delivery

Manual diff submission can be used before GitHub integration. For PR events, configure a repository webhook at `https://your-host/webhooks/github`, a matching `EVOAGENT_GITHUB_WEBHOOK_SECRET`, JSON payloads and supported pull-request events. Keep the local service behind the intended HTTPS forwarding/reverse-proxy setup. A GitHub token is needed for private repositories, comment posting or other authorized write actions. The repository-webhook path does not require installing a GitHub App.

Check GitHub Recent Deliveries, the HTTP response and the saved task independently. Optional posting is enabled by `EVOAGENT_AUTO_POST_REVIEW=true`; review completion and comment delivery are separate outcomes. Do not infer a working external integration from unit tests alone.

## Main API routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Local health/configuration status. |
| POST | `/v1/auth/login` | Login and obtain a scoped token. |
| POST | `/v1/reviews` | Submit a review; `?async=true` creates asynchronous work. |
| GET | `/v1/tasks/{id}` | Task state, execution trace and report. |
| GET | `/v1/tasks/{id}/report` | Markdown report. |
| GET/POST | `/v1/tasks/{id}/feedback` | Inspect or submit scoped task feedback. |
| POST | `/v1/tasks/{id}/cancel` | Request cancellation. |
| POST | `/v1/tasks/{id}/resume` | Resume compatible saved work. |
| POST | `/webhooks/github` | Receive PR webhook events. |
| POST | `/v1/skills/reload` | Reload declarative Skills. |
| POST | `/v1/evolution/auto` or `/v1/evolution/propose` | Replay prompt candidates. |
| POST | `/v1/skill-evolution/auto` or `/v1/skill-evolution/propose` | Build/evaluate Skill candidates. |
| GET/POST | `/v1/evaluation/cases` | Versioned evaluation cases. |
| GET | `/metrics` | Prometheus-format metrics. |

Additional rollout, queue, audit and repair interfaces are implemented in `evoagent/api.py`. Their presence is not proof of production deployment, historical version acceptance or unrestricted repair support.

## Declarative Skills

A package under `skills/<name>/` contains `SKILL.md` with YAML frontmatter and review instructions. `name` matches the directory; `description` supports discovery; `allowed-tools` declares permitted registered tools. Runtime permissions also intersect role-level permissions. Skills do not install network connectors or grant arbitrary filesystem access.

The selected Skill body supplies the worker's task boundary, investigation steps, evidence/severity criteria, false-positive checks and output contract. Optional text resources remain inside the package. Keep stable global rules in the global prompt when they do not need independent selection or evolution. Inspect candidate evaluation, provenance and publication separately.

## Regression and evidence boundaries

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The tests use controlled dependencies. Offline fixture metrics and a single unlabelled real-PR pilot measure different things; they are not interchangeable accuracy evidence. Keep real environment files, credentials, application databases, caches and dependency environments outside Git. The current interface language is unchanged by this documentation translation.
