# Agent Skill 演进：验证 SKILL.md 制品，回放基线和候选，按租户保存版本、激活或回滚。

"""Replay-gated evolution of standard Agent Skill ``SKILL.md`` packages."""
import hashlib
import json
import re
import threading
import uuid
from typing import Any, Callable, Dict, Optional

from .diff_parser import parse_unified_diff
from .evolution import EvolutionEngine, RegressionEvaluator
from .reviewer import Reviewer
from .skills import AgentSkill, SKILL_NAME
from .store import utc_now


ARTIFACT_SCHEMA_VERSION = 2
RULE_ID = re.compile(r"[A-Z][A-Z0-9_-]{1,79}")


# 按稳定的键顺序生成紧凑 JSON，供内容比较和指纹计算使用。
def _canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# 计算内容的 SHA-256 指纹，用于识别相同输入和追踪版本。
def _sha256(value: dict) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


# 生成具备标准 frontmatter 的初始 Skill 文本，作为演进基线。
def _default_skill_markdown(name: str) -> str:
    return """---
name: %s
description: Apply replay-validated review guidance learned from confirmed feedback. Use during code review when project-specific failure patterns may apply.
---

# Review project-specific failure patterns

Inspect the current change using repository evidence. Report only actionable defects introduced by added lines, and include a concrete fix and regression test.
""" % name


# 将旧版规则制品转换为标准 SKILL.md 包，保留兼容读取能力。
def _migrate_legacy_artifact(artifact: dict, expected_name: str) -> dict:
    name = str(artifact.get("name", expected_name)).strip().lower()
    description = str(artifact.get("description") or (
        "Apply migrated project-specific guidance during code review."
    )).replace("\n", " ").strip()
    lines = [
        "---", "name: %s" % name,
        "description: %s" % json.dumps(description, ensure_ascii=False), "---", "",
        "# Migrated review guidance", "",
        "Apply these checks to added production lines and verify repository context.", "",
    ]
    for rule in artifact.get("rules") or []:
        rule_id = str(rule.get("rule_id", "REVIEW")).strip().upper()
        match = str(rule.get("match", "")).replace("`", "'").strip()
        if not match:
            continue
        lines.extend([
            "<!-- evoagent:learned:%s:start -->" % rule_id,
            "## %s" % rule_id, "",
            "Inspect added behavior equivalent to `%s`." % match,
            "Report `%s` at `%s` severity only when context confirms the defect."
            % (rule_id, str(rule.get("severity", "medium"))),
            "Cite the changed line, explain impact, propose a fix, and require a test.",
            "<!-- evoagent:learned:%s:end -->" % rule_id, "",
        ])
    return {"name": name, "files": {"SKILL.md": "\n".join(lines).strip() + "\n"}}


# 检查 Skill 制品结构与名称，规范化 SKILL.md 和资源并计算内容指纹。
def validate_artifact(artifact: Any, expected_name: str = "") -> dict:
    """Validate and canonicalize one versioned Agent Skill package."""
    expected_name = str(expected_name).strip().lower()
    if expected_name and not SKILL_NAME.fullmatch(expected_name):
        raise ValueError("invalid Agent Skill name")
    if isinstance(artifact, str):
        artifact = {"name": expected_name, "files": {"SKILL.md": artifact}}
    if not isinstance(artifact, dict):
        raise ValueError("agent skill artifact must be an object")
    if "rules" in artifact and "files" not in artifact and "skill_md" not in artifact:
        artifact = _migrate_legacy_artifact(artifact, expected_name)
    if "skill_md" in artifact and "files" not in artifact:
        artifact = {
            **artifact,
            "files": {
                "SKILL.md": artifact.get("skill_md"),
                **dict(artifact.get("supporting_files") or {}),
            },
        }
    name = str(artifact.get("name", expected_name)).strip().lower()
    if expected_name and name != expected_name:
        raise ValueError("agent skill artifact name must match skill_name")
    skill = AgentSkill.from_artifact({
        "name": name, "files": dict(artifact.get("files") or {}),
    })
    normalized = skill.to_artifact()
    normalized["schema_version"] = ARTIFACT_SCHEMA_VERSION
    return normalized


# Skill 回放的最小任务存储适配器。
class _ReplayTaskStore:
    # 保存回放任务所需的最小输入，供候选 Skill 审查时读取。
    def __init__(self, skill_name: str):
        self.skill_name = skill_name

    # 提供当前 Skill 回放任务的输入配置，适配产品审查器的存储接口。
    def get(self, _task_id: str, _tenant_id: Optional[str] = None) -> dict:
        return {"input": {
            "mode": "agentic",
            "enabled_agents": ["lead", "security", "correctness-reliability", "critic"],
            "enabled_skills": [self.skill_name],
        }}


# 将候选 Skill 注入真实 Agent 协作流程进行回放。
class AgentSkillReplayReviewer(Reviewer):
    """Replay a candidate through the product Lead/worker Skill runtime."""

    # 校验候选制品并构造使用该 Skill 的 Agent 审查链路与预算。
    def __init__(self, artifact: dict, client, token_budget: int = 8000, time_budget_seconds: int = 60):
        from .agentic_core import AgenticReviewer

        self.skill = AgentSkill.from_artifact(artifact)
        self.name = "%s-agent-skill-replay" % self.skill.name
        self._sequence = 0
        self._last_task_id = ""
        self.token_budget = int(token_budget)
        self.time_budget_seconds = int(time_budget_seconds)
        self.agentic = AgenticReviewer(
            _ReplayTaskStore(self.skill.name), client,
            default_token_budget=token_budget,
            default_time_budget=time_budget_seconds,
            skill_provider=lambda _tenant: [self.skill],
        )

    # 为制品回放构造默认案例上下文，再进入完整 Agent 协作审查。
    def review(self, diff: str, parsed) -> list:
        return self.review_case({"diff": diff, "repository": ""}, parsed)

    # 接收完整案例上下文后执行审查，供评测器记录仓库和任务元信息。
    def review_case(self, case: dict, parsed) -> list:
        self._sequence += 1
        self._last_task_id = "skill-replay:%s:%d" % (self.skill.name, self._sequence)
        return self.agentic.review_with_context(
            self._last_task_id, case["diff"], parsed,
            repository=str(case.get("repository_root") or case.get("repository") or ""),
        )

    # 返回最近一次评测调用的执行账本，供成本和调用次数统计。
    def evaluation_execution(self) -> dict:
        return dict(
            self.agentic.collaboration_summary(self._last_task_id).get("execution") or {}
        )

    # 返回最近一次审查的协作摘要，供实验验证实际角色拓扑。
    def evaluation_collaboration(self) -> dict:
        return dict(
            self.agentic.collaboration_summary(self._last_task_id).get("collaboration") or {}
        )

    # 导出当前评测组的配置，便于核对和复现实验。
    def evaluation_config(self) -> dict:
        return {
            "mode": "agentic", "roles": [
                "lead", "security", "correctness-reliability", "critic",
            ],
            "skill": self.skill.name,
            "per_role_token_budget": self.token_budget,
            "per_role_time_budget_seconds": self.time_budget_seconds,
        }


# 按租户管理 Skill 制品候选、回放门禁和版本切换。
class SkillEvolutionEngine:
    """Create, replay, activate and roll back Agent Skill package versions."""

    # 保存租户制品存储、回放工厂和门禁参数，用锁串行化候选版本变更。
    def __init__(
        self, store, reviewer_factory: Optional[Callable[[dict], Reviewer]] = None,
        min_cases: int = 3, max_cases: int = 100, min_improvement: float = .01,
        min_holdout_cases: int = 2, max_metric_regression: float = 0.0,
    ):
        self.store = store
        self.reviewer_factory = reviewer_factory
        self.min_cases = min_cases
        self.max_cases = max_cases
        self.min_improvement = min_improvement
        self.min_holdout_cases = min_holdout_cases
        self.max_metric_regression = max_metric_regression
        self._lock = threading.RLock()

    # 创建指定 Skill 的初始制品，用于尚无活动版本时的基线比较。
    @staticmethod
    def empty_artifact(skill_name: str) -> dict:
        return validate_artifact(_default_skill_markdown(skill_name), skill_name)

    # 在已有 Skill 内容上构造候选制品，并通过统一验证后返回。
    @classmethod
    def build_candidate_artifact(
        cls, skill_name: str, base_artifact: dict, feedback: list,
    ) -> dict:
        """Pure artifact mutation used by controlled and production experiments.

        Feedback must already contain concrete evidence; no task-store lookup is
        performed here. This keeps experiment arms isolated and reproducible.
        """
        artifact = validate_artifact(base_artifact, skill_name)
        content = artifact["files"]["SKILL.md"]
        learned, removed, used = [], [], []
        for index, case in enumerate(feedback):
            finding = (case.get("payload") or {}).get("finding") or {}
            rule_id = str(finding.get("rule_id", "")).strip().upper()
            if not RULE_ID.fullmatch(rule_id):
                continue
            category = str(case.get("category", ""))
            if category == "false_positive":
                updated = cls._remove_learned_block(content, rule_id)
                if updated != content:
                    content = updated
                    removed.append(rule_id)
                    used.append(case.get("id", index))
                continue
            if category != "missed_issue":
                continue
            evidence = str(finding.get("evidence", "")).strip()
            if not evidence or len(evidence) > 240 or "\n" in evidence or "\r" in evidence:
                continue
            if "evoagent:learned:%s:start" % rule_id in content:
                continue
            content = content.rstrip() + "\n\n" + cls._learned_block(
                rule_id, finding, evidence,
            )
            learned.append(rule_id)
            used.append(case.get("id", index))
        candidate = validate_artifact({
            "name": skill_name,
            "files": {**artifact["files"], "SKILL.md": content},
        }, skill_name)
        return {
            "artifact": candidate,
            "learned_rule_ids": sorted(set(learned)),
            "removed_rule_ids": sorted(set(removed)),
            "used_feedback_ids": used,
        }

    # 从序列化的制品创建回放审查器，适配通用回归评测接口。
    def _factory(self, serialized: str) -> Reviewer:
        if self.reviewer_factory is None:
            raise RuntimeError("Agent Skill replay requires a configured model")
        return self.reviewer_factory(json.loads(serialized))

    # 裁剪保留集的公开结果，避免暴露逐案例明细。
    @staticmethod
    def _redact_holdout(metrics: dict) -> dict:
        return {key: value for key, value in metrics.items() if key not in {"case_results", "errors"}}

    # 逐项比较候选与基线的受保护指标，允许配置范围内的浮动。
    def metrics_non_regressing(self, candidate: dict, baseline: dict) -> bool:
        protected = ["score", "precision", "recall", "high_severity_recall", "success_rate"]
        if baseline.get("positive_cases", 0):
            protected.append("severity_accuracy")
        if baseline.get("clean_cases", 0):
            protected.append("clean_accuracy")
        return all(
            float(candidate.get(key, 0)) + self.max_metric_regression
            >= float(baseline.get(key, 0)) for key in protected
        )

    # 逐项检查受保护指标，判断候选的退步是否超过允许范围。
    def _non_regressing(self, candidate: dict, baseline: dict) -> bool:
        return self.metrics_non_regressing(candidate, baseline)

    # 返回当前 Skill 演进配置、样本就绪状态和活动版本信息。
    def status(self, skill_name: str = "evolved-review", tenant_id: str = "default") -> dict:
        validation = self.store.list_evaluation_cases("validation", True, self.max_cases)
        holdout = self.store.list_evaluation_cases("holdout", True, self.max_cases)
        active = self.store.get_active_skill_artifact(skill_name, tenant_id)
        return {
            "tenant_id": tenant_id, "skill_name": skill_name, "format": "agent-skill",
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "active_version": active.get("version") if active else None,
            "active_artifact_sha256": active.get("artifact_sha256") if active else None,
            "validation_cases": len(validation), "holdout_cases": len(holdout),
            "minimum_cases": self.min_cases, "minimum_holdout_cases": self.min_holdout_cases,
            "minimum_improvement": self.min_improvement,
            "maximum_metric_regression": self.max_metric_regression,
            "model_configured": self.reviewer_factory is not None,
            "ready": self.reviewer_factory is not None
            and len(validation) >= self.min_cases and len(holdout) >= self.min_holdout_cases,
        }

    # 规范化 Skill 名称并校验制品，在锁内完成候选评测和保存。
    def propose(self, skill_name: str, artifact: Any, tenant_id: str = "default", *, manual=False, feedback_ids=()) -> dict:
        skill_name = skill_name.strip().lower()
        candidate = validate_artifact(artifact, skill_name)
        with self._lock:
            return self._propose(skill_name, candidate, tenant_id, manual, feedback_ids)

    # 在相同验证集与保留集回放基线和候选，满足改进及非退步条件才激活。
    def _propose(self, skill_name: str, artifact: dict, tenant_id: str, manual=False, feedback_ids=()) -> dict:
        active = self.store.get_active_skill_artifact(skill_name, tenant_id)
        baseline_artifact = (
            validate_artifact(active["artifact"], skill_name)
            if active else self.empty_artifact(skill_name)
        )
        # 内容未变时直接延后，不制造重复版本，也不额外消耗模型回放。
        if active and _sha256(baseline_artifact) == _sha256(artifact):
            return {
                "version": self._public_version(active), "decision": "deferred",
                "reason": "candidate Agent Skill is identical to the active version",
                "candidate": {}, "baseline": {}, "candidate_holdout": {},
                "baseline_holdout": {}, "gates": {}, "run_id": None,
            }
        validation = self.store.list_evaluation_cases("validation", True, self.max_cases)
        holdout = self.store.list_evaluation_cases("holdout", True, self.max_cases)
        baseline_metrics = self._empty_metrics(len(validation))
        candidate_metrics = self._empty_metrics(len(validation))
        baseline_holdout = self._empty_metrics(len(holdout))
        candidate_holdout = self._empty_metrics(len(holdout))
        decision, reason = "deferred", ""
        gates = {
            "artifact_valid": True, "runtime_is_agent_skill": True,
            "model_configured": self.reviewer_factory is not None,
            "validation_dataset_ready": len(validation) >= self.min_cases,
            "holdout_dataset_ready": len(holdout) >= self.min_holdout_cases,
            "evaluation_success": None, "validation_improvement": None,
            "validation_non_regression": None, "holdout_non_regression": None,
        }
        if self.reviewer_factory is None:
            reason = "candidate saved but no model-backed Agent Skill replay is configured"
        elif len(validation) < self.min_cases:
            reason = "candidate saved but the validation dataset is smaller than the activation minimum"
        elif len(holdout) < self.min_holdout_cases:
            reason = "candidate saved but the holdout dataset is smaller than the activation minimum"
        else:
            evaluator = RegressionEvaluator(self._factory)
            baseline_metrics = evaluator.run(_canonical_json(baseline_artifact), validation)
            candidate_metrics = evaluator.run(_canonical_json(artifact), validation)
            baseline_holdout = evaluator.run(_canonical_json(baseline_artifact), holdout)
            candidate_holdout = evaluator.run(_canonical_json(artifact), holdout)
            no_errors = not (
                baseline_metrics["errors"] or candidate_metrics["errors"]
                or baseline_holdout["errors"] or candidate_holdout["errors"]
            )
            improved = candidate_metrics["score"] >= baseline_metrics["score"] + self.min_improvement
            validation_safe = self._non_regressing(candidate_metrics, baseline_metrics)
            holdout_safe = self._non_regressing(candidate_holdout, baseline_holdout)
            gates.update({
                "evaluation_success": no_errors, "validation_improvement": improved,
                "validation_non_regression": validation_safe,
                "holdout_non_regression": holdout_safe,
            })
            if no_errors and improved and validation_safe and holdout_safe:
                decision = "ready" if manual else "activated"
                reason = "candidate SKILL.md improved validation and passed holdout non-regression"
            else:
                decision = "rejected"
                failures = []
                if not no_errors:
                    failures.append("evaluation failed")
                if not improved:
                    failures.append("validation improvement was below threshold")
                if not validation_safe:
                    failures.append("a protected validation metric regressed")
                if not holdout_safe:
                    failures.append("a protected holdout metric regressed")
                reason = "; ".join(failures)
        version = self.store.save_skill_artifact(
            skill_name, artifact, candidate_metrics.get("score", 0.0),
            decision == "activated", tenant_id,
        )
        candidate_change = self._skill_diff(baseline_artifact, artifact)
        run = {
            "id": str(uuid.uuid4()), "tenant_id": tenant_id, "skill_name": skill_name,
            "candidate_version": version["version"],
            "baseline_version": active.get("version") if active else None,
            "decision": decision, "candidate_score": candidate_metrics.get("score", 0.0),
            "baseline_score": baseline_metrics.get("score", 0.0), "created_at": utc_now(),
            "metrics": {
                "candidate": candidate_metrics, "baseline": baseline_metrics,
                "candidate_holdout": self._redact_holdout(candidate_holdout),
                "baseline_holdout": self._redact_holdout(baseline_holdout),
                "gates": gates, "reason": reason, "candidate_change": candidate_change,
                "feedback_ids": list(feedback_ids),
                "reproducibility": {
                    "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
                    "candidate_artifact_sha256": version["artifact_sha256"],
                    "validation_dataset_sha256": EvolutionEngine._dataset_fingerprint(validation),
                    "holdout_dataset_sha256": EvolutionEngine._dataset_fingerprint(holdout),
                    "baseline_artifact_sha256": active.get("artifact_sha256")
                    if active else _sha256(baseline_artifact),
                },
            },
        }
        self.store.save_skill_evolution_run(run)
        return {
            "version": version, "decision": decision, "reason": reason,
            "candidate": candidate_metrics, "baseline": baseline_metrics,
            "candidate_holdout": self._redact_holdout(candidate_holdout),
            "baseline_holdout": self._redact_holdout(baseline_holdout),
            "gates": gates, "run_id": run["id"], "candidate_change": candidate_change,
        }

    # 将确认漏报写入 Skill 指导块，移除误报对应块；候选激活后再解决已用反馈。
    def auto_propose(
        self, skill_name: str = "evolved-review", tenant_id: Optional[str] = None,
        *, manual=False,
    ) -> dict:
        skill_name = skill_name.strip().lower()
        if not SKILL_NAME.fullmatch(skill_name):
            raise ValueError("invalid Agent Skill name")
        failures = self.store.list_failure_cases(
            True, 100, tenant_id, skill_name=skill_name,
        )
        tenant_id = tenant_id or "default"
        active = self.store.get_active_skill_artifact(skill_name, tenant_id)
        artifact = (
            validate_artifact(active["artifact"], skill_name)
            if active else self.empty_artifact(skill_name)
        )
        content = artifact["files"]["SKILL.md"]
        used_ids, learned, removed = [], [], []
        for case in failures:
            finding = (case.get("payload") or {}).get("finding") or {}
            rule_id = str(finding.get("rule_id", "")).strip().upper()
            if not RULE_ID.fullmatch(rule_id):
                continue
            if case.get("category") == "false_positive":
                updated = self._remove_learned_block(content, rule_id)
                marker = f"<!-- evoagent:false-positive:{rule_id} -->"
                if manual and updated == content and marker not in content:
                    updated = (content.rstrip() + f"\n\n{marker}\nFor `{rule_id}`, confirm the failing preconditions and "
                               "check whether repository controls already prevent the claimed impact before reporting.\n")
                if updated != content:
                    content = updated
                    removed.append(rule_id)
                    used_ids.append(case["id"])
                continue
            if manual and case.get("category") == "bad_fix":
                marker = f"<!-- evoagent:bad-fix:{rule_id} -->"
                if marker not in content:
                    content = (content.rstrip() + f"\n\n{marker}\nFor `{rule_id}`, preserve existing valid behavior "
                               "in the proposed fix and specify a regression test for the affected boundary.\n")
                    used_ids.append(case["id"])
                continue
            if case.get("category") != "missed_issue":
                continue
            evidence = str(finding.get("evidence", "")).strip()
            if not evidence:
                evidence = self._evidence_from_task(case["task_id"], finding)
            if not evidence or len(evidence) > 240 or "\n" in evidence or "\r" in evidence:
                continue
            if "evoagent:learned:%s:start" % rule_id in content:
                continue
            content = content.rstrip() + "\n\n" + self._learned_block(rule_id, finding, evidence)
            learned.append(rule_id)
            used_ids.append(case["id"])
        if not used_ids:
            return {
                "version": None, "decision": "deferred",
                "reason": "no supported SKILL.md mutation signal was found in unresolved feedback",
                "failure_cases_used": len(failures), "learned_rule_ids": [],
                "removed_rule_ids": [], "run_id": None,
            }
        candidate = validate_artifact({
            "name": skill_name,
            "files": {**artifact["files"], "SKILL.md": content},
        }, skill_name)
        result = self.propose(skill_name, candidate, tenant_id, manual=manual, feedback_ids=used_ids)
        result.update({
            "failure_cases_used": len(used_ids),
            "learned_rule_ids": sorted(set(learned)),
            "removed_rule_ids": sorted(set(removed)),
        })
        # 只有候选真正激活后才解决相关反馈；被拒或延后的候选仍保留学习信号。
        if result["decision"] == "activated":
            self.store.resolve_failure_cases(used_ids)
        return result

    # 把确认的问题类型与短证据生成带规则标记的 Skill 指导块。
    @staticmethod
    def _learned_block(rule_id: str, finding: dict, evidence: str) -> str:
        evidence = evidence.replace("`", "'")
        severity = str(finding.get("severity", "medium")).lower()
        return "\n".join([
            "<!-- evoagent:learned:%s:start -->" % rule_id,
            "## Confirmed %s guidance" % rule_id, "",
            "Inspect added behavior equivalent to `%s`." % evidence,
            "Report `%s` at `%s` severity only when repository context confirms the defect."
            % (rule_id, severity),
            "Cite the changed line, explain impact, propose a minimal fix, and require a regression test.",
            "<!-- evoagent:learned:%s:end -->" % rule_id, "",
        ])

    # 按规则标记移除误报反馈对应的已学习段落。
    @staticmethod
    def _remove_learned_block(content: str, rule_id: str) -> str:
        pattern = re.compile(
            r"\n*<!-- evoagent:learned:%s:start -->.*?"
            r"<!-- evoagent:learned:%s:end -->\n*" % (re.escape(rule_id), re.escape(rule_id)),
            re.DOTALL,
        )
        return pattern.sub("\n", content).rstrip() + "\n"

    # 从原任务的 Diff 或报告中查找反馈位置对应的代码证据。
    def _evidence_from_task(self, task_id: str, finding: dict) -> str:
        diff = self.store.get_task_payload(task_id)
        if not diff:
            return ""
        try:
            path, line = str(finding.get("path", "")), int(finding.get("line", 0))
            for changed in parse_unified_diff(diff).added_lines:
                if changed.path == path and changed.line == line:
                    return changed.content.strip()
        except (TypeError, ValueError):
            return ""
        return ""

    # 将指定租户的 Skill 恢复到已有版本。
    def rollback(self, skill_name: str, version: int, tenant_id: str = "default") -> bool:
        return self.store.activate_skill_artifact(skill_name, version, tenant_id)

    # 生成基线与候选 SKILL.md 的文本差异，供人工检查演进内容。
    @staticmethod
    def _skill_diff(baseline: dict, candidate: dict) -> dict:
        before, after = baseline.get("files") or {}, candidate.get("files") or {}
        names = sorted(set(before).union(after))
        return {
            "changed_files": [name for name in names if before.get(name) != after.get(name)],
            "baseline_skill_md_sha256": hashlib.sha256(
                str(before.get("SKILL.md", "")).encode("utf-8")
            ).hexdigest(),
            "candidate_skill_md_sha256": hashlib.sha256(
                str(after.get("SKILL.md", "")).encode("utf-8")
            ).hexdigest(),
        }

    # 在尚未回放或回放不可用时返回统一的空指标结构。
    @staticmethod
    def _empty_metrics(cases: int) -> Dict[str, Any]:
        return {
            "schema_version": 2, "reviewer": "", "score": 0.0,
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "severity_accuracy": 0.0, "high_severity_recall": 0.0,
            "clean_accuracy": 0.0, "cases": cases, "positive_cases": 0,
            "clean_cases": 0, "expected_findings": 0, "predicted_findings": 0,
            "successful_cases": 0, "success_rate": 0.0, "errors": [],
            "case_results": [],
        }

    # 提取版本公开信息，避免在每个状态响应中重复返回完整制品。
    @staticmethod
    def _public_version(value: dict) -> dict:
        return {
            key: value[key] for key in (
                "tenant_id", "skill_name", "version", "score", "active", "parent_version",
                "artifact_sha256", "created_at",
            ) if key in value
        }
