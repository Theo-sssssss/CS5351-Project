# Run and Verify the Selected EvoAgent Source

Use `submission/EvoAgent-Final-Source.zip`, rebuilt from the updated `EvoAgent 2` folder supplied on 27 November 2026. Current source hashes are recorded in `evidence/release/current-delivery-update.json`; the GitHub source commit is `e48ee634b7f609a89f761adc8b7a516cb8fcba31`. Extract it into a new working directory. The ZIP contains a root folder named `EvoAgent`.

## Create an environment

Python 3.11 is recommended. On macOS or Linux, run these commands from the extracted `EvoAgent` folder:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Only copy the example when no real `.env` already exists. Preserve existing configuration. On Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The dependency list includes PyYAML. An import failure for `yaml` means the test environment has not installed the required dependency.

## Run local regression

On macOS or Linux:

```bash
.venv/bin/python --version
.venv/bin/python -m pip freeze
.venv/bin/python -m unittest discover -s tests -q
```

On Windows, substitute `.\.venv\Scripts\python.exe` for `.venv/bin/python`.

The current source ZIP passed 89 tests on 27 November 2026 using Python 3.11.5 after extraction without a real `.env`. See `evidence/release/latest-source-tests.txt`, `latest-source-test-run.json` and `latest-source-dependencies.txt`. Repeated OpenTelemetry TracerProvider override messages were logged without test failures. Preserve the current run record and source identity for later verification.

## Reproduce the current offline metrics

The current source was rerun on 27 November with the checked-in 100-case controlled corpus and separate 130-case prompt fixture. See `evidence/evaluation/current-source-20261127/README.md` for commands, exact metrics, dataset/source hashes and the no-LLM execution boundary. Use new output directories for an independent run.

## Configure and start

The example environment file lists supported settings. Supply your own valid model configuration, credentials, and authentication settings. Keep secrets local and excluded from Git.

For an OpenAI-compatible endpoint, the configuration uses `EVOAGENT_LLM_PROVIDER=custom`, `EVOAGENT_LLM_BASE_URL`, `EVOAGENT_LLM_API_KEY`, and `EVOAGENT_LLM_MODEL`. If authentication is enabled, configure a strong local administrator password and a random authentication secret according to `.env.example` and the source documentation.

```bash
.venv/bin/python -m evoagent
```

Open `http://127.0.0.1:8080/`. A local SQLite setup does not require PostgreSQL or Redis. A service that starts without a configured model has not yet passed live model-review acceptance.

## Demonstration and acceptance

Use an authorized test repository or a frozen manual diff. Record the input revision, model configuration, budget, task state, report revision, coverage, and usage. Check pause/resume and confirmation if presenting those capabilities. Use separate evidence for actual GitHub webhook delivery, comment posting, or repair publication.

The current supplied video replaces the earlier deterministic-fixture recording. Its playback, duration and content checks were waived by the user on 27 November; do not infer its execution mode from the historical fixture trace. The public PR pilot in `evidence/evaluation/` records real-model execution. Identify these two evidence types accurately in the presentation.

## Report delivery

The report PDF and LaTeX source remain local and are intentionally excluded from this upload.

## Current presentation and demo status

The current deck is `submission/EvoAgent-Presentation.pptx`, with a matching PDF and updated speaking notes. The earlier slide LaTeX source has been retired. The updated user-supplied demonstration is packaged as `submission/EvoAgent-Demo.mp4`. Video inspection was waived by the user. Presentation rehearsal remains a team delivery activity. Website translation to English is deferred at the user's request. See the process index in `process/README.md`.
