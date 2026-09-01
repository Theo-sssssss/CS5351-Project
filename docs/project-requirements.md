# Project Requirements and Team Baseline / 项目要求与团队执行基线

## 1. Project Objective / 项目目标

Build an original software engineering tool that helps programmers or development teams perform a development task. Suitable directions include code review, testing, debugging, code-smell detection, technical-debt management, requirement tracking, or an extension to an existing developer tool.

构建一个帮助程序员或开发团队完成开发任务的原创软件工程工具。可选方向包括代码审查、测试、调试、代码异味检测、技术债管理、需求追踪，或对现有开发工具的扩展。

The project must not be an ordinary end-user application, an e-commerce system, a library system, or only a machine-learning model/training script.

项目不能是普通面向用户的应用、电商系统、图书馆系统，或仅仅是机器学习模型/训练脚本。

## 2. Scope Rules / 范围规则

- Start from an observable developer-workflow pain point. / 从一个可观察到的开发流程痛点出发。
- State the user, workflow, trigger, current failure, measurable outcome, and explicit non-goals before implementation. / 实现前明确用户、工作流程、触发条件、当前失败点、可衡量结果和明确的非目标。
- Prefer a focused component, plugin, or improvement to an existing open-source tool over a full-featured tool. / 优先选择聚焦的组件、插件或现有开源工具的改进，不做功能大而全的工具。
- Establish a baseline before introducing the new solution, then measure the change using pre-defined tasks, data, metrics, thresholds, and test cases. / 引入新方案前建立基线；使用预先定义的任务、数据、指标、阈值和测试用例衡量改进。

## 3. Six-Person Team Requirements / 六人团队要求

- Each member should contribute about 30-40 productive hours. / 每位成员应贡献约 30-40 小时的有效工作时间。
- Contributions are reported in the final report and may be used to prorate individual marks. / 最终报告须说明贡献，且贡献可能用于按比例计算个人成绩。
- Track contribution using hours or story points, including difficult technical tasks. / 使用工时或故事点追踪贡献，并体现高难度技术任务。
- Record each member's code, tests, reviews, experiments, documentation, and process contributions through commits, issues, and pull requests. / 通过提交、Issue 和 Pull Request 记录每位成员的代码、测试、评审、实验、文档与过程贡献。

## 4. Process Requirements / 过程要求

The team uses at least three Agile sprints:

团队至少进行三个敏捷 Sprint：

| Sprint / 冲刺 | Weeks / 周次 | Required focus / 核心工作 |
| --- | --- | --- |
| Sprint 1 | 2-5 | User stories, architecture, implementation, testing, review, and technical-debt tracking / 用户故事、架构、实现、测试、评审和技术债追踪 |
| Sprint 2 | 6-9 | Sprint 1 activities plus code quality / Sprint 1 的活动加上代码质量 |
| Sprint 3 | 10-13 | Sprint 2 activities plus automated testing, debugging, and maintenance support / Sprint 2 的活动加上自动化测试、调试和维护支持 |

Run at least one standing meeting per week and maintain a project burndown chart.

每周至少举行一次固定例会，并维护项目燃尽图。

## 5. Non-Functional Requirements / 非功能需求

For a team of six, define at least two non-functional requirements. Each must be addressed by a documented architectural design option and rationale.

六人团队至少要定义两项非功能需求。每一项都必须有文档化的架构设计选择及其理由。

Candidate requirements to evaluate after scope selection:

选题确定后可评估的候选需求：

- Performance / 性能: acceptable latency or throughput for the intended repository or data size / 对目标仓库或数据规模具有可接受的延迟或吞吐量。
- Scalability / 可扩展性: predictable behavior as source files, projects, or analysis tasks grow / 随源文件、项目或分析任务增长仍有可预测的表现。
- Reliability / 可靠性: recoverable failures, deterministic analysis, and actionable error reporting / 可恢复的故障、确定性的分析和可操作的错误报告。
- Usability / 易用性: low setup cost and an understandable developer workflow / 低配置成本且开发者流程易于理解。
- Maintainability / 可维护性: modular boundaries, tests, and clear extension points / 模块边界、测试和清晰的扩展点。
- Security/privacy / 安全与隐私: safe treatment of source code, credentials, and external service data / 安全处理源代码、凭证和外部服务数据。

## 6. Repository Evidence Standard / 仓库证据规范

- Plan work as visible issues with acceptance criteria. / 使用带验收标准的公开 Issue 规划工作。
- Link pull requests to the issues they implement. / 将 Pull Request 与其实现的 Issue 关联。
- Preserve code, tests, review discussion, architecture decisions, technical debt, risks, and weekly sprint evidence. / 保留代码、测试、评审讨论、架构决策、技术债、风险和每周 Sprint 证据。
- Keep a risk register with risk, trigger, likelihood, impact, owner, mitigation, and decision date. / 维护风险登记表，包含风险、触发条件、可能性、影响、负责人、缓解措施和决策日期。
- Use CI status checks to make test and policy evidence visible on pull requests when the implementation is ready. / 实现准备好后，使用 CI 状态检查在 Pull Request 中展示测试和策略证据。

## 7. Deliverables / 交付物

- Presentation slides in Week 12, covering background, motivation, related work, problem, solution, challenges, innovation, and evaluation. / 第 12 周提交展示幻灯片，涵盖背景、动机、相关工作、问题、方案、挑战、创新和评估。
- Demo video showing significant end-to-end uses and the development process. / 演示视频应展示最重要的端到端使用流程和开发过程。
- Final report and source code in Week 13. / 第 13 周提交最终报告和源代码。
- Final report of about 10,000 words excluding figures, tables, self-reflection, and references, using the IEEE Transactions on Software Engineering format. / 最终报告约 10,000 词，不含图表、自我反思和参考文献，采用 IEEE Transactions on Software Engineering 格式。

## 8. Initial Role Coverage / 初始职责覆盖

The team should ensure that these responsibilities are owned, while sharing review and implementation work:

团队应明确下列职责的负责人，同时共同参与评审和实现：

| Area / 领域 | Primary responsibility / 主要职责 |
| --- | --- |
| Product and process / 产品与过程 | Scope, backlog, meetings, burndown, risks / 范围、待办列表、会议、燃尽图、风险 |
| Architecture and core engine / 架构与核心引擎 | Technical design and key algorithm / 技术设计和关键算法 |
| Integration and user workflow / 集成与用户流程 | CLI, plugin, web interface, or tool integration / CLI、插件、Web 界面或工具集成 |
| Evaluation and data / 评估与数据 | Baselines, data, metrics, experiment scripts / 基线、数据、指标、实验脚本 |
| Testing and quality / 测试与质量 | Test strategy, CI, reviews, technical debt / 测试策略、CI、评审、技术债 |
| Documentation and demonstration / 文档与演示 | Report, diagrams, slides, and demo video / 报告、图表、幻灯片和演示视频 |
