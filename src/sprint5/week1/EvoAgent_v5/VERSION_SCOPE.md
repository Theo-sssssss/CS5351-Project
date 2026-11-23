# EvoAgent V5 — Restored Controlled Skill Evolution Snapshot

This folder was reconstructed from the available complete EvoAgent source after
the original `EvoAgent_v5` archive could no longer be found locally.

V5 builds on V4's adaptive review with **controlled Skill Evolution**:

- feedback is converted into candidate review-skill artifacts;
- candidates are replayed against validation and holdout cases;
- activation requires explicit replay gates and supports rollback;
- automated testing, failure diagnosis, and maintenance checks are available
  through `scripts/run_maintenance.py`.

The snapshot deliberately excludes local secrets, databases, virtual
environments, caches, IDE settings, and Git metadata. The copied source also
contains later shared infrastructure so it remains buildable with the complete
project; the V5 scope above is the feature boundary to present and evaluate.

```bash
python3 -m pip install -r requirements.txt
python3 scripts/run_maintenance.py
```
