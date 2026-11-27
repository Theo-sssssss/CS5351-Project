# Run EvoAgent Locally

Extract the source archive and enter its `EvoAgent` directory, which contains `requirements.txt`. Python 3.11 is recommended.

## Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

## macOS / Linux

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
```

Preserve an existing `.env`. Local SQLite use does not require PostgreSQL or Redis.

## Configure and start

Use your own valid model configuration. An OpenAI-compatible endpoint needs `EVOAGENT_LLM_PROVIDER=custom`, `EVOAGENT_LLM_BASE_URL`, `EVOAGENT_LLM_API_KEY` and `EVOAGENT_LLM_MODEL`. The DeepSeek preset uses `EVOAGENT_LLM_PROVIDER=deepseek` and `EVOAGENT_DEEPSEEK_API_KEY`. Configure authentication/admin settings as described in `README.md` when authentication is enabled.

Start with `.venv/bin/python -m evoagent` on macOS/Linux or `.\.venv\Scripts\python.exe -m evoagent` on Windows. Open `http://127.0.0.1:8080/`.

A service can start without a configured model, but a model-backed review needs a working provider. Begin with a manual diff if appropriate, then configure GitHub intake separately. Keep local keys and databases outside the distributed archive.
