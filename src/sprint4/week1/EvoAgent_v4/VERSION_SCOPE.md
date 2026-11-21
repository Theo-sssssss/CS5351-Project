# EvoAgent V4 — Restored Adaptive Review Snapshot

This folder was reconstructed from the available complete EvoAgent source after
the original `EvoAgent_v4` archive could no longer be found locally.

V4's intended increment is **adaptive review**:

- risk-aware context selection for changed code;
- repository-scoped review memory and feedback recall;
- declarative, role-scoped review skills;
- bounded agent runtime, checkpointing, and evidence gates.

The snapshot deliberately excludes local secrets, databases, virtual
environments, caches, IDE settings, and Git metadata. The copied source also
contains later shared infrastructure so it remains buildable with the complete
project; the V4 scope above is the feature boundary to present and evaluate.

To install dependencies and run the automated tests:

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```
