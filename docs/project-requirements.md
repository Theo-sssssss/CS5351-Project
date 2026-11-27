# Project Requirements and Team Baseline

## 1. Project Objective

Build an original software engineering tool that helps programmers or development teams perform a development task. Suitable directions include code review, testing, debugging, code-smell detection, technical-debt management, requirement tracking, or an extension to an existing developer tool.

The project must not be an ordinary end-user application, an e-commerce system, a library system, or only a machine-learning model/training script.

## 2. Scope Rules

- Start from an observable developer-workflow pain point.
- State the user, workflow, trigger, current failure, measurable outcome, and explicit non-goals before implementation.
- Prefer a focused component, plugin, or improvement to an existing open-source tool over a full-featured tool.
- Establish a baseline before introducing the new solution, then measure the change using pre-defined tasks, data, metrics, thresholds, and test cases.

## 3. Six-Person Team Requirements

- Each member should contribute about 30-40 productive hours.
- Contributions are reported in the final report and may be used to prorate individual marks.
- Track contribution using hours or story points, including difficult technical tasks.
- Record each member's code, tests, reviews, experiments, documentation, and process contributions through commits, issues, and pull requests.

## 4. Process Requirements

The team uses at least three Agile sprints:

| Sprint | Weeks | Required focus |
| --- | --- | --- |
| Sprint 1 | 2-5 | User stories, architecture, implementation, testing, review, and technical-debt tracking |
| Sprint 2 | 6-9 | Sprint 1 activities plus code quality |
| Sprint 3 | 10-13 | Sprint 2 activities plus automated testing, debugging, and maintenance support |

Run at least one standing meeting per week and maintain a project burndown chart.

## 5. Non-Functional Requirements

For a team of six, define at least two non-functional requirements. Each must be addressed by a documented architectural design option and rationale.

Candidate requirements to evaluate after scope selection:

- Performance: acceptable latency or throughput for the intended repository or data size
- Scalability: predictable behavior as source files, projects, or analysis tasks grow
- Reliability: recoverable failures, deterministic analysis, and actionable error reporting
- Usability: low setup cost and an understandable developer workflow
- Maintainability: modular boundaries, tests, and clear extension points
- Security/privacy: safe treatment of source code, credentials, and external service data

## 6. Repository Evidence Standard

- Plan work as visible issues with acceptance criteria.
- Link pull requests to the issues they implement.
- Preserve code, tests, review discussion, architecture decisions, technical debt, risks, and weekly sprint evidence.
- Keep a risk register with risk, trigger, likelihood, impact, owner, mitigation, and decision date.
- Use CI status checks to make test and policy evidence visible on pull requests when the implementation is ready.

## 7. Deliverables

- Presentation slides in Week 12, covering background, motivation, related work, problem, solution, challenges, innovation, and evaluation.
- Demo video showing significant end-to-end uses and the development process.
- Final report and source code in Week 13.
- Final report of about 10,000 words excluding figures, tables, self-reflection, and references, using the IEEE Transactions on Software Engineering format.

## 8. Initial Role Coverage

The team should ensure that these responsibilities are owned, while sharing review and implementation work:

| Area | Primary responsibility |
| --- | --- |
| Product and process | Scope, backlog, meetings, burndown, risks |
| Architecture and core engine | Technical design and key algorithm |
| Integration and user workflow | CLI, plugin, web interface, or tool integration |
| Evaluation and data | Baselines, data, metrics, experiment scripts |
| Testing and quality | Test strategy, CI, reviews, technical debt |
| Documentation and demonstration | Report, diagrams, slides, and demo video |
