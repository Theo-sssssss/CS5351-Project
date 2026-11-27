# Skill 演进测试：覆盖标准包加载、Worker 使用、候选回放、反馈学习与租户版本覆盖。

import json
import os
import tempfile
import unittest

from evoagent.config import Settings
from evoagent.diff_parser import parse_unified_diff
from evoagent.service import ReviewService
from evoagent.skill_evolution import (
    AgentSkillReplayReviewer,
    SkillEvolutionEngine,
    validate_artifact,
)
from evoagent.skills import AgentSkill, SkillRegistry
from evoagent.store import TaskStore


RISK_DIFF = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+dangerous_call(data)\n"
CLEAN_DIFF = "--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-old\n+safe_call(data)\n"


# 生成包含合法 frontmatter 与指导正文的测试 Skill 文本。
def skill_markdown(name="review-dangerous-calls", include_rule=True):
    guidance = (
        "\n## Confirmed SEC-DANGEROUS-CALL guidance\n\n"
        "Inspect added behavior equivalent to `dangerous_call(data)`.\n"
        "Report `SEC-DANGEROUS-CALL` at `high` severity when context confirms it.\n"
        if include_rule else ""
    )
    return """---
name: %s
description: Review added code for confirmed project-specific dangerous calls.
---

# Review dangerous calls

Use changed-line evidence and report only actionable defects.%s
""" % (name, guidance)


# 将测试 Skill 文本包装成标准版本制品。
def artifact(name="review-dangerous-calls", include_rule=True):
    return validate_artifact(skill_markdown(name, include_rule), name)


# 本组测试的可控替身，用预设响应隔离外部依赖。
class SkillAwareClient:
    provider = "fake"
    model = "skill-aware"

    # 按角色和输入上下文返回确定性 JSON，并记录测试需要核对的调用信息。
    def complete_json(self, role, _system, user, ledger=None, max_tokens=None):
        if ledger:
            ledger.record_model(role, self.provider, self.model, {
                "prompt_tokens": 10, "completion_tokens": 5,
            }, 1)
        managed = json.loads(user)
        task = json.loads(managed["task"])
        if role == "lead":
            if task["phase"] == "delegate":
                requested = task.get("requested_agent_skills") or []
                selected = requested or [
                    item["name"] for item in task.get("available_agent_skills") or []
                ]
                return {"action": "final", "delegations": [{
                    "assignment_id": "security-1", "worker": "security",
                    "objective": "Review project-specific dangerous calls",
                    "skills": selected,
                }], "risk_level": "normal"}
            if task["phase"] == "assess-workers":
                return {"action": "final", "revision_requests": [], "critic_objective": "Verify"}
            if task["phase"] == "finalize":
                return {
                    "action": "final",
                    "accepted_finding_indices": list(range(len(task["candidate_findings"]))),
                    "confidence_adjustments": [],
                }
        if role == "security":
            instructions = "\n".join(
                item.get("instructions", "") for item in task.get("active_agent_skills") or []
            )
            rendered_diff = json.dumps(task["diff"], ensure_ascii=False)
            if "dangerous_call(data)" in instructions and "dangerous_call(data)" in rendered_diff:
                return {"action": "final", "findings": [{
                    "rule_id": "SEC-DANGEROUS-CALL", "severity": "high",
                    "title": "Dangerous call", "explanation": "Confirmed unsafe API was added.",
                    "path": "a.py", "line": 1, "evidence": "dangerous_call(data)",
                    "fix": "Use safe_call instead.", "test": "Add a regression test.",
                    "confidence": .9,
                    "call_chain": [{"path": "a.py", "line": 1, "symbol": "dangerous_call"}],
                }]}
            return {"action": "final", "findings": []}
        if role == "correctness-reliability":
            return {"action": "final", "findings": []}
        if role == "critic":
            return {"action": "final", "decisions": [{
                "finding_index": index, "accepted": True, "objections": [],
                "confidence_adjustment": 0.0,
            } for index, _item in enumerate(task["candidates"])]}
        raise AssertionError(role)


# 集中验证本模块的正常行为、错误路径及数据边界。
class SkillEvolutionTests(unittest.TestCase):
    # 为每个测试创建独立夹具和临时资源，避免前一个用例的状态影响当前断言。
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.store = TaskStore(self.path)
        self.client = SkillAwareClient()

    # 释放本用例创建的资源并清理临时数据，保持测试之间互不干扰。
    def tearDown(self):
        os.unlink(self.path)

    # 在测试数据库中写入验证与保留案例，满足演进门禁的样本要求。
    def seed_cases(self):
        self.store.save_evaluation_case(
            "danger-validation", "validation", RISK_DIFF,
            [{"path": "a.py", "line": 1, "rule_id": "SEC-DANGEROUS-CALL", "min_severity": "high"}],
            "test",
        )
        self.store.save_evaluation_case("clean-holdout", "holdout", CLEAN_DIFF, [], "test")

    # 构造使用测试回放器的 Skill 演进引擎。
    def engine(self):
        return SkillEvolutionEngine(
            self.store,
            reviewer_factory=lambda value: AgentSkillReplayReviewer(value, self.client),
            min_cases=1, max_cases=10, min_improvement=.01, min_holdout_cases=1,
        )

    # 验证标准 SKILL.md 包及资源可被加载，无需执行 Python 插件代码。
    def test_registry_loads_standard_skill_and_resources_without_python(self):
        with tempfile.TemporaryDirectory() as root:
            directory = os.path.join(root, "review-dangerous-calls")
            os.makedirs(os.path.join(directory, "references"))
            with open(os.path.join(directory, "SKILL.md"), "w", encoding="utf-8") as handle:
                handle.write(skill_markdown())
            with open(os.path.join(directory, "references", "policy.md"), "w", encoding="utf-8") as handle:
                handle.write("Use safe_call.\n")
            with open(os.path.join(directory, "skill.py"), "w", encoding="utf-8") as handle:
                handle.write("raise RuntimeError('must never be imported')\n")
            registry = SkillRegistry(root)
            registry.reload()
            loaded = registry.get_agent_skill("review-dangerous-calls")
            self.assertIsNotNone(loaded)
            self.assertEqual("Use safe_call.\n", loaded.read_resource("references/policy.md"))
            self.assertEqual("agent-skill", registry.list()[0]["kind"])
            os.unlink(os.path.join(directory, "SKILL.md"))
            registry.reload()
            self.assertIsNone(registry.get_agent_skill("review-dangerous-calls"))

    # 验证随项目提供的 Agent Skill 可以被目录扫描发现。
    def test_bundled_agent_skills_are_discoverable(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills"))
        registry = SkillRegistry(root)
        registry.reload()
        self.assertEqual({
            "api-compatibility", "code-quality", "correctness-review",
            "database-review", "observability-review", "performance-review",
            "reliability-review", "security-review", "test-quality",
        }, {item["name"] for item in registry.catalog()})
        for item in registry.list():
            self.assertEqual("agent-skill", item["kind"])
            self.assertTrue(item["description"])

    # 验证 Skill 必须有合法 frontmatter，且名称与目录一致。
    def test_skill_md_requires_frontmatter_and_matching_directory_name(self):
        with self.assertRaisesRegex(ValueError, "frontmatter"):
            AgentSkill.from_markdown("# Missing metadata")
        with self.assertRaisesRegex(ValueError, "match"):
            AgentSkill.from_markdown(
                skill_markdown("review-dangerous-calls"),
                expected_name="different-name",
            )

    # 验证分派到的 Skill 正文进入 Worker 的真实执行上下文。
    def test_agent_skill_body_is_selected_and_runs_through_worker_graph(self):
        reviewer = AgentSkillReplayReviewer(artifact(), self.client)
        findings = reviewer.review(RISK_DIFF, parse_unified_diff(RISK_DIFF))
        self.assertEqual(["SEC-DANGEROUS-CALL"], [item.rule_id for item in findings])
        summary = reviewer.agentic.collaboration_summary("skill-replay:review-dangerous-calls:1")
        self.assertEqual(["review-dangerous-calls"], summary["collaboration"]["agent_skills"])

    # 验证候选 Skill 经回放放行后激活并持久化。
    def test_candidate_skill_md_replay_activates_and_persists(self):
        self.seed_cases()
        result = self.engine().propose("review-dangerous-calls", artifact())
        self.assertEqual("activated", result["decision"])
        active = self.store.get_active_skill_artifact("review-dangerous-calls")
        self.assertEqual("agent-skill", active["artifact"]["format"])
        self.assertIn("SKILL.md", active["artifact"]["files"])
        self.assertEqual(2, active["artifact"]["schema_version"])
        self.assertEqual(["SKILL.md"], result["candidate_change"]["changed_files"])

    # 验证确认的反馈学习结果写入 SKILL.md 指导块。
    def test_auto_evolution_writes_learned_guidance_into_skill_md(self):
        self.seed_cases()
        self.store.create("task", "org/repo", 1, {"source": "test"})
        self.store.save_task_payload("task", RISK_DIFF)
        self.store.record_failure_case("task", "missed_issue", {"finding": {
            "rule_id": "SEC-DANGEROUS-CALL", "severity": "high", "path": "a.py", "line": 1,
        }}, "review-dangerous-calls")
        result = self.engine().auto_propose("review-dangerous-calls")
        self.assertEqual("activated", result["decision"])
        content = self.store.get_active_skill_artifact(
            "review-dangerous-calls"
        )["artifact"]["files"]["SKILL.md"]
        self.assertIn("Confirmed SEC-DANGEROUS-CALL guidance", content)
        self.assertIn("dangerous_call(data)", content)
        self.assertTrue(self.store.list_failure_cases()[0]["resolved"])

    # 验证自动演进只消费归属于目标 Skill 的反馈，其他领域反馈保持待处理。
    def test_auto_evolution_does_not_absorb_other_skill_feedback(self):
        self.seed_cases()
        for task_id in ("target-task", "other-task"):
            self.store.create(task_id, "org/repo", 1, {"source": "test"})
            self.store.save_task_payload(task_id, RISK_DIFF)
        self.store.record_failure_case("target-task", "missed_issue", {"finding": {
            "rule_id": "SEC-DANGEROUS-CALL", "severity": "high", "path": "a.py", "line": 1,
        }}, "review-dangerous-calls")
        self.store.record_failure_case("other-task", "missed_issue", {"finding": {
            "rule_id": "DB-UNBOUNDED-QUERY", "severity": "medium", "path": "db.py", "line": 9,
            "evidence": "query_without_limit()",
        }}, "database-review")

        result = self.engine().auto_propose("review-dangerous-calls")

        self.assertEqual(["SEC-DANGEROUS-CALL"], result["learned_rule_ids"])
        target = self.store.list_failure_cases(skill_name="review-dangerous-calls")[0]
        unrelated = self.store.list_failure_cases(skill_name="database-review")[0]
        self.assertTrue(target["resolved"])
        self.assertFalse(unrelated["resolved"])

    # 验证活动 Skill 按租户隔离，并在该租户中覆盖同名磁盘版本。
    def test_active_agent_skills_are_tenant_isolated_and_override_disk(self):
        self.store.save_skill_artifact(
            "review-dangerous-calls", artifact(), 1.0, True, "tenant-a",
        )
        with tempfile.TemporaryDirectory() as skills_dir:
            settings = Settings(
                host="127.0.0.1", port=8080, db_path=self.path,
                max_diff_bytes=10000, max_steps=8, timeout_seconds=10,
                llm_base_url="", llm_api_key="", llm_model="",
                github_webhook_secret="", github_token="", auto_post_review=False,
                skills_dir=skills_dir, eval_min_holdout_cases=0,
            )
            service = ReviewService(settings)
            service.chat_client = self.client
            service.reviewer = service._build_agentic_reviewer()
            service.harness.reviewer = service.reviewer
            try:
                self.assertIn(
                    "review-dangerous-calls", {item["name"] for item in service.list_skills("tenant-a")}
                )
                self.assertNotIn(
                    "review-dangerous-calls", {item["name"] for item in service.list_skills("tenant-b")}
                )
                report = service.create_review(
                    "org/repo", RISK_DIFF, tenant_id="tenant-a",
                    enabled_skills=["review-dangerous-calls"],
                )["report"]
                self.assertIn(
                    "SEC-DANGEROUS-CALL", [item["rule_id"] for item in report["findings"]]
                )
            finally:
                service.queue.close()


if __name__ == "__main__":
    unittest.main()
