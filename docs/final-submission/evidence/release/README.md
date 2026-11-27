# Release evidence identities

## Current local delivery — 27 November 2026

- `current-delivery-update.json`: manifest of 99 current source files and the retained video identity.
- `latest-source-test-run.json`: current source ZIP hash, Python environment, command and result (89 tests passed).
- `latest-source-tests.txt`: full verbose output, including non-failing OpenTelemetry provider messages.
- `latest-source-dependencies.txt`: packages in the Python environment used for this run.

The tests ran on a fresh extraction without a real `.env` or provider/GitHub environment overrides. This used an existing dependency environment, not a new dependency installation. A separate current-source controlled offline rerun is recorded in `../evaluation/current-source-20261127/`; no live-model accuracy or performance study was added. The updated source is commit `e48ee634b7f609a89f761adc8b7a516cb8fcba31` on `main`.

## Historical baseline

Other archived release-verification files in this directory identify the earlier `b9a63e3` baseline. They are retained unchanged for provenance and do not describe the current refreshed archive. The current offline rerun is identified in `../evaluation/current-source-20261127/`; older evaluation and real-model pilot files retain their original source and input scope.
