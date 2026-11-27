# EvoAgent V2 — Fixed Collaborative Review

V2 belongs to course Sprint 2. It retains the single-call baseline and adds fixed collaboration: Lead planning, Security Worker, Correctness/Reliability Worker, Critic checking and final synthesis. Both modes share intake, SQLite storage, the UI and programmatic diff-evidence gates.

| Capability | Baseline | Collaborative |
| --- | --- | --- |
| Model calls | Fixed one | Fixed five |
| Specialist/Critic stages | No | Yes |
| Evidence gate | Yes | Yes |
| Role trace and usage | Yes | Yes |

V2 does not implement autonomous tool loops, repository memory, Skills, checkpoint resume or unrestricted repair. Those are later-version concerns.

## Start

Python 3.10+ is required; no third-party dependency is needed for this version.

```bash
cd src/sprint2/week1/EvoAgent_v2
cp -n .env.example .env
# Configure the compatible model endpoint, API key and model name.
./start.sh
```

Open `http://127.0.0.1:8083/`. Prefer `EVOAGENT_V2_LLM_CHAT_COMPLETIONS_URL` for an exact endpoint. When only a base URL is configured, the client appends `/chat/completions`. Preserve existing local configuration. Private repositories and comment posting require appropriate GitHub permissions.

## Workflow and API

The UI can run `baseline`, `collaborative` or a paired comparison for one PR. Task details show final findings, rejected candidates, role states/traces, token/call accounting, diff size and separate GitHub delivery status.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Configuration/TLS status. |
| GET | `/api/tasks` | Recent tasks. |
| GET | `/api/tasks/{id}` | Report, role traces and metrics. |
| POST | `/api/reviews/from-pr` | Create a baseline or collaborative task. |
| POST | `/api/reviews/compare` | Compare both modes on the same PR. |
| POST | `/webhooks/github` | Receive signed PR events. |

A publishable finding must match a changed file, added-line location and quoted diff evidence. Oversized diffs fail explicitly. A failed GitHub comment delivery does not delete a successful stored report. Source correspondence does not prove semantic defect validity.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py evoagent_v2/*.py
node --check static/app.js
sh -n start.sh
```

Tests use controlled dependencies and do not call real GitHub/model services. The archived regression records 33 passing tests. See [V2 Review](../../../../docs/final-submission/process/V2-Review.md) and [V2 Retrospective](../../../../docs/final-submission/process/V2-Retrospective.md).

V3 adds bounded read-only tools, runtime budgets and checkpoints. Preserve the same input and finding contract when comparing versions. Keep credentials/databases local and expose only the necessary webhook endpoint for public integration.
