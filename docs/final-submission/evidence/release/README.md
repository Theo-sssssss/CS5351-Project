# Release Evidence Identities

## Current delivery — 28 November 2026

The refreshed English-documentation source is commit `ce27a3a5c85db15312a3bbf746d44754ca918b36`. Its archive contains 99 distributable files. Only `README.md` and `RUN-LOCAL.md` differ from the 27 November tested archive; the other 97 files, including executable sources, configuration and evaluation fixtures, are byte-identical.

- `current-delivery-update.json`: source-file fingerprints, documentation equivalence and the retained video identity.
- `latest-source-test-run.json`: refreshed source ZIP hash, Python environment, command and 89-test passing result.
- `latest-source-tests.txt`: full verbose output, including non-failing OpenTelemetry provider messages.
- `latest-source-dependencies.txt`: packages in the existing Python environment used for the run.

The regression ran on a fresh extraction without a real `.env` or provider/GitHub environment overrides. This reused an existing dependency environment. The offline evaluations in `../evaluation/current-source-20261127/` retain their original measured archive hash. Their implementation and input files are unchanged; translation is not a new accuracy measurement. No new live-model result is claimed.

## Historical baseline

Other archived release-verification files identify the earlier `b9a63e3` baseline and are retained unchanged for provenance. The archived real-model pilot also retains its original source and input scope.
