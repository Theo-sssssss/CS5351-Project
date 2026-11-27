# EvoAgent V4 — Adaptive Review Snapshot

V4 belongs to course Sprint 3. Its intended increment is risk-aware bounded context, repository-scoped feedback memory and declarative role-scoped review Skills. See [VERSION_SCOPE.md](VERSION_SCOPE.md) for the attribution boundary. The restored source also includes shared later infrastructure; controlled Skill evolution is the V5 increment rather than a new V4 feature inferred from every included module.

## Historical verification

The initial restored V4 regression ran 70 tests with one failure and five errors. A maintained local copy restored two fixture files and replaced a quotation-sensitive assertion with a structural check, then passed 70 tests with remaining ResourceWarnings. That pass identifies the maintained local copy and is not a fresh pass of the unchanged repository snapshot. See [V4 Review](../../../../docs/final-submission/process/V4-Review.md), [V4 Retrospective](../../../../docs/final-submission/process/V4-Retrospective.md) and the archived before/after logs.

Use the [current V5 source](../../../sprint5/week1/EvoAgent_v5) and its packaged fixtures for the verified final delivery. The shared setup and interface descriptions below explain the integrated service, not a claim that all later modules were first delivered in V4.

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
