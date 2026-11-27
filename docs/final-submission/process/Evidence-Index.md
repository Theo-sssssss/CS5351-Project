# EvoAgent Repository and Evaluation Evidence

Group 04. Team name: **group**. Updated on 28 November 2026.

Repository: [Theo-sssssss/CS5351-Project](https://github.com/Theo-sssssss/CS5351-Project). The checkpoints below identify fixed artifacts; a source commit is not presented as the moving head of `main`.

## Current published checkpoints

| Evidence | Fixed revision / file | Scope |
| --- | --- | --- |
| Verified V5 source | [e48ee63](https://github.com/Theo-sssssss/CS5351-Project/tree/e48ee634b7f609a89f761adc8b7a516cb8fcba31/src/sprint5/week1/EvoAgent_v5) | 99 source files matching the tested archive, plus two repository description files |
| Non-report delivery files | [61c6b2f](https://github.com/Theo-sssssss/CS5351-Project/tree/61c6b2f6861dd72fc2c20bf7df3aedbc1aef7086/docs/final-submission) | Completed V5 records, presentation, demo, source archive and verification outputs |
| Weekly screenshots | [Current evidence](https://github.com/Theo-sssssss/CS5351-Project/tree/main/docs/evidence) | 11 original calendar screenshots and file checksums |
| Current source identity | [Release identity](../evidence/release/current-delivery-update.json) | Source hashes and uploaded source revision |
| Current regression | [Run record](../evidence/release/latest-source-test-run.json), [full log](../evidence/release/latest-source-tests.txt), [dependencies](../evidence/release/latest-source-dependencies.txt) | 89 passes, zero failures/errors; Python 3.11.5; fresh archive extraction using an existing dependency environment |
| Current offline comparison | [Summary](../evidence/evaluation/current-source-20261127/README.md), [raw JSON](../evidence/evaluation/current-source-20261127/controlled-evaluation.json), [run metadata](../evidence/evaluation/current-source-20261127/run-metadata.json) | Fixed synthetic data, source/dataset hashes, seed and commands; no real LLM calls |
| Prompt replay | [Raw replay](../evidence/evaluation/current-source-20261127/prompt-evolution-proof.json) | Separate 130-case fixture; numerical success and production activation decision are distinct |

## Current-source metrics

| Full-workflow measurement | Cases | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Aggregate: train + validation + holdout | 100 | 100.00% | 82.50% | 90.41% |
| Held-out subset | 20 | 100.00% | 62.50% | 76.92% |

The full workflow with an evolved Skill has the same scores: zero matched holdout F1 gain. The repository-disjoint split is 60/20/20. The separate Skill-policy comparison and prompt replay are described in the current summary and must not be pooled with these scores. Prompt replay improved fixture F1 from 66.67% to 100% while production activation remained blocked by provenance. Its isolated offline `activated` decision does not mean production publication.

## Historical runtime and model evidence

The [deterministic trace](../evidence/evaluation/demo-trace.json) records budget pause at 2/12 batches, resume to 12/12, and report revision confirmation. It is an archived fixture walkthrough. Current batching behavior also has regression coverage in the 89-test source. The supplied MP4 is a separate artifact; its content and execution mode were not inferred from that trace because video inspection was waived.

The [paired public-PR pilot](../evidence/evaluation/paired-pilot.json) and [batched result](../evidence/evaluation/arm-batched.json) retain the original frozen input: one unlabelled documentation PR. The batched run completed in 27.415 seconds using 9,262 recorded tokens; the legacy path exceeded its budget after 45.876 seconds. No new pilot was run during the current offline rerun, and these observations do not estimate real-world precision or recall.

## Increment references

| Increment | Commit date in GMT+8 | Commit | Source location |
| --- | --- | --- | --- |
| V1 core | 13 September 2026 | [5f88441](https://github.com/Theo-sssssss/CS5351-Project/commit/5f884417baa71975b898eeef8a469d126815b829) | `src/sprint1/week1/EvoAgent_v1` |
| V1 source restoration | 22 September 2026 | [258b304](https://github.com/Theo-sssssss/CS5351-Project/commit/258b304f041af6457af73f247838c84aef9e013d) | Same V1 source path |
| V2 | 18 October 2026 | [f231554](https://github.com/Theo-sssssss/CS5351-Project/commit/f2315543fd577c573d1e629d9e39750107047a40) | `src/sprint2/week1/EvoAgent_v2` |
| V3 | 7 November 2026 | [aefe1f7](https://github.com/Theo-sssssss/CS5351-Project/commit/aefe1f741cebf4e840b76726c84be5668a476c1d) | `src/sprint3/week1/EvoAgent_v3` |
| V4 restored snapshot | 21 November 2026 | [7a866fa](https://github.com/Theo-sssssss/CS5351-Project/commit/7a866faddaca3d715b987a1325bf7f2a7772ca5d) | `src/sprint4/week1/EvoAgent_v4` |
| Final-delivery snapshot | 21 November 2026 | [b9a63e3](https://github.com/Theo-sssssss/CS5351-Project/commit/b9a63e3097635cc5d6f6bad14b82732da43dba02) | `src/final/EvoAgent` on the delivery branch |
| V5 original restored snapshot | 23 November 2026 | [faf93a1](https://github.com/Theo-sssssss/CS5351-Project/commit/faf93a111f24bff749a8dc1c26c9aa56bddf2b88) | `src/sprint5/week1/EvoAgent_v5` |
| V5 verified refresh | 28 November 2026 | [e48ee63](https://github.com/Theo-sssssss/CS5351-Project/commit/e48ee634b7f609a89f761adc8b7a516cb8fcba31) | `src/sprint5/week1/EvoAgent_v5` |

## Weekly discussion evidence

The [calendar screenshot index](https://github.com/Theo-sssssss/CS5351-Project/tree/main/docs/evidence) links all 11 originals from Week 02 through Week 12. The dated entries establish scheduled appointments, while the team separately confirmed attendance for meetings already held. Screenshots do not establish individual authorship or ceremony decisions.

| Sprint | Planning | Review | Retrospective |
| --- | --- | --- | --- |
| 1 | 7 September 2026 | 2 October 2026 | 2 October 2026 |
| 2 | 12 October 2026 | 6 November 2026 | 6 November 2026 |
| 3 | 9 November 2026 | 27 November 2026 | 27 November 2026 |

The Sprint 3 Review and Retrospective checkpoint is 27 November; the formal Sprint period ends on 30 November. V3's 7 November upload followed the 6 November Review and is recorded as Sprint-end follow-up.

## Completion and contribution evidence

Use the [completed V5 record](V5-Sprint-Backlog-Review-Retrospective.md) and [member allocation](Contribution-Traceability.md) together. Backlogs and team confirmation establish ownership and actual hours; source, tests and experiment outputs establish software behavior. Centralized uploads do not imply sole authorship. The report and personal report statements remain local and are not part of this push.
