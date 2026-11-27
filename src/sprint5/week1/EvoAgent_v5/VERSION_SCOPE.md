# EvoAgent V5 — Verified Delivery Refresh

Group 04. Team name: group. Updated on 28 November 2026.

V5's increment is controlled Skill evolution from repository feedback through candidate artifacts, fixed validation/holdout evaluation and gated publication or rollback. This refreshed delivery also includes the integrated final workflow: batch coverage, bounded model/tool execution, checkpoint resume, report revision confirmation and deterministic checks for removed Python guards.

The 99 source files match the tested local source archive. The extracted archive passed 89 regression tests using Python 3.11.5 on 27 November. A separate current-source run reproduced the 100-case controlled offline comparison and 130-case prompt replay. These fixture runs do not invoke a real LLM or establish real-PR accuracy. Source identity, complete test logs, raw evaluation outputs and delivery documents are under `docs/final-submission/` at the repository root.

`VERSION_SCOPE.md` and `EVALUATION_RESULTS.md` are repository documentation added alongside the 99 source files. Earlier versions remain available in Git history. Real `.env` files, application databases, caches and dependency environments are excluded.

## Run

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

See the repository-level `docs/final-submission/RUN-AND-VERIFY.md` for configuration and evaluation instructions.
