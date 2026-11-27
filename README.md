# EvoAgent — CS5351 Group 04

**Team name: group.** EvoAgent helps developers review pull requests through evidence-linked findings, bounded agent execution, visible review coverage and controlled updates to review configuration.

## Start here

| Material | Location |
| --- | --- |
| Current V5 source | [Source and setup guide](src/sprint5/week1/EvoAgent_v5) |
| Presentation and demo | [PowerPoint](docs/final-submission/submission/EvoAgent-Presentation.pptx), [slides PDF](docs/final-submission/submission/EvoAgent-Presentation.pdf), [demo video](docs/final-submission/submission/EvoAgent-Demo.mp4) |
| Process records | [Sprint and version index](docs/final-submission/process) |
| Individual contributions | [Version hours, completed V5 tasks and evidence](docs/final-submission/process/Contribution-Traceability.md) |
| Weekly discussion evidence | [Eleven original calendar screenshots](docs/evidence) |
| Testing and evaluation | [Regression record](docs/final-submission/evidence/release/latest-source-test-run.json), [offline results](docs/final-submission/evidence/evaluation/current-source-20261127/README.md) |
| Reproduction instructions | [Run and verify](docs/final-submission/RUN-AND-VERIFY.md) |

## What the tool does

- Accepts a unified diff or a GitHub pull request and returns structured findings tied to changed-code evidence.
- Coordinates Lead, specialist and Critic roles under tool permissions and resource limits.
- Reviews large changes in batches, exposes completed/outstanding coverage and resumes from saved checkpoints.
- Stores repository/tenant-scoped feedback and supports declarative review Skills.
- Replays candidate Skill or prompt changes before allowing eligible publication or rollback.

The two non-functional requirements are **security and isolation** and **reliability and recoverability**. Source, tests and process records document the relevant authority boundaries, task states, checkpoints and acceptance criteria.

## Three Sprints, five versions

The global version numbering is unchanged: **V1 belongs to Sprint 1; V2/V3 to Sprint 2; V4/V5 to Sprint 3.** Repository folders named `sprint1` through `sprint5` are version-storage paths, not five course Sprints.

| Global version | Course Sprint | Main increment | Review | Retrospective |
| --- | --- | --- | --- | --- |
| V1 | Sprint 1 | Single-call review baseline | [Review](docs/final-submission/process/V1-Review.md) | [Retrospective](docs/final-submission/process/V1-Retrospective.md) |
| V2 | Sprint 2 | Fixed collaboration and diff-evidence gates | [Review](docs/final-submission/process/V2-Review.md) | [Retrospective](docs/final-submission/process/V2-Retrospective.md) |
| V3 | Sprint 2 | Bounded tools, budgets and checkpoint recovery | [Review](docs/final-submission/process/V3-Review.md) | [Retrospective](docs/final-submission/process/V3-Retrospective.md) |
| V4 | Sprint 3 | Adaptive context, scoped memory and declarative Skills | [Review](docs/final-submission/process/V4-Review.md) | [Retrospective](docs/final-submission/process/V4-Retrospective.md) |
| V5 | Sprint 3 | Controlled evolution and integrated delivery | [Completed Review and Retrospective](docs/final-submission/process/V5-Sprint-Backlog-Review-Retrospective.md) | Same combined record |

V3's upload followed the Sprint 2 ceremony, and the V4 maintenance pass identifies a repaired local copy. Their records preserve those distinctions instead of inferring historical sign-off from upload dates.

## Verification results

The packaged current-source regression passed **89 tests**. The run record retains its archive hash, Python environment and full output.

| Controlled full-workflow measurement | Cases | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Aggregate: train + validation + holdout | 100 | 100.00% | 82.50% | 90.41% |
| Separate held-out subset | 20 | 100.00% | 62.50% | 76.92% |

These fixture results use deterministic rules and simulated model clients, with no real LLM calls. The evolved Skill gave zero matched holdout F1 gain. The separate prompt replay improved fixture F1 while production activation remained blocked by provenance. An archived single-public-PR pilot measures execution completion; it does not establish real-PR accuracy. See the [evidence index](docs/final-submission/process/Evidence-Index.md) for the exact scope of each result.

## Run locally

From the repository root:

```bash
cd src/sprint5/week1/EvoAgent_v5
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
```

Configure your model endpoint/key and authentication settings in the local `.env`, then start:

```bash
.venv/bin/python -m evoagent
```

Open `http://127.0.0.1:8080/`. Follow the [V5 guide](src/sprint5/week1/EvoAgent_v5/README.md) for model configuration, authentication, API routes and webhook setup. Real credentials, application databases and dependency environments stay outside Git.

## Team and delivery status

Jiexuan Shen, Jiayu Zhu, Siye Tu, Tianyi Jiang, Jianyu Zhou and Xinyu Zhang each recorded **36 hours**, totaling **216 team hours**. Members handed their outputs to Jiexuan Shen for integration and centralized uploads. Backlogs and the confirmed contribution table record individual responsibility.

The source, English process documents, presentation, supplied demo and verification evidence are published here. **The report PDF, LaTeX source and personal report statements remain local and are intentionally not pushed.** Presentation rehearsal and official submission remain team delivery activities. Website translation was deferred; original screenshot evidence is preserved unchanged.
