# Public PR paired pilot

The two final-release engines reviewed the same frozen documentation diff from [Click PR 88](https://github.com/pallets/click/pull/88). Both used MiMo v2.6 Pro, an initial task token budget of 12,000 and a configured timeout setting of 20 seconds. The engine modes can apply limits differently internally. Separate local SQLite databases were used and posting was disabled. The snapshot checksum and PR revision metadata are in `pr-88.json`.

| Engine | Outcome | Elapsed | Recorded tokens | Coverage |
| --- | --- | ---: | ---: | --- |
| Legacy | Task execution budget exceeded | 45.876 s | Unavailable | Unavailable |
| Batched | Success, zero findings | 27.415 s | 9,262 | 1 of 1 batches |

The reported time is client elapsed time. The single sample has no independently reviewed ground truth. Zero findings and the completion gap cannot establish comparative review accuracy or general reliability.

The first two paired attempts failed TLS certificate verification under system Python. A sequential retry with the system CA bundle reached its 150-second outer deadline. An independent model request on the same frozen diff succeeded in 7.511 seconds and used 1,105 tokens. Two time-bounded engine processes then produced the results above. `paired-pilot.json` is the consolidated run, and the per-arm files preserve the individual records.

The separate demonstration trace runs the service with a deterministic fixture and verifies pause, resume and confirmation.

## Current source rerun

See [27 November current-source offline evaluation](current-source-20261127/README.md) for newly executed precision, recall and F1, aggregate and held-out counts, prompt replay gates, source/dataset hashes and reproducible commands. Older V5 results and real-PR pilot files are retained as historical evidence.
