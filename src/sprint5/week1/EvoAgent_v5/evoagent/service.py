# 应用服务层：组装模型、工具、存储、队列和演进组件，为 API 提供审查、修复与反馈入口。

import hashlib
from copy import copy
from threading import Timer
import uuid
from typing import Any, Dict, Optional

from .agentic_core import AgenticReviewer
from .auth import AuthManager
from .batch_review import BatchReview, ENGINE, ReviewConflict, SNAPSHOT, checkpoint
from .config import Settings
from .context_manager import ContextManager
from .evolution import EvolutionEngine
from .evolution_v2 import RootCauseEvolutionGenerator
from .fixer import SafeFixer
from .patching import SuggestionOnlyFixer, VerifiedPatchFixer
from .github import GitHubAppAuthenticator, GitHubClient
from .github_review import GitHubReview
from .harness import ReviewHarness
from .metrics import metrics
from .llm import JsonChatClient, ModelResponseError
from .modes import RunMode
from .memory import MemoryManager
from .models import TaskState, TraceEvent
from .observability import AlertManager, Observability
from .postgres_store import create_store
from .runtime import RuntimeBudgetExceeded
from .reviewer import OpenAICompatibleReviewer
from .skills import AgentSkill, SKILL_NAME, SkillRegistry
from .skill_evolution import AgentSkillReplayReviewer, SkillEvolutionEngine, validate_artifact
from .store import utc_now
from .task_queue import PermanentTaskError, QueueLeaseBusy, TaskQueue
from .rollout import ReleaseManager
from .verifier import RepairVerifier
from .workbench import ReviewWorkbench


# API 与基础组件之间的应用服务，协调审查、修复和反馈闭环。
class ReviewService:
    # 先校验配置，再组装存储、模型、工作流、认证、演进与异步队列依赖。
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.validate_evolution()
        self.llm_config = settings.resolved_llm()
        self.store = create_store(settings.database_url, settings.db_path)
        self.memory = MemoryManager(
            self.store, settings.memory_enabled, settings.memory_recall_limit,
            settings.memory_working_ttl_seconds,
        )
        self.context_manager = ContextManager(
            settings.agent_context_window_tokens,
            settings.agent_context_input_tokens,
            settings.context_diff_token_budget,
            settings.context_observation_token_budget,
            settings.context_recent_observations,
            settings.context_map_chunk_tokens,
        )
        self.observability = Observability(settings.otel_service_name, settings.otel_endpoint)
        self.registry = SkillRegistry(settings.skills_dir)
        if self.llm_config:
            active = self.store.get_active_skill_version("llm-review")
            self.registry.register(
                "llm-review",
                self._build_llm_reviewer(active["prompt"] if active else ""),
                "1.0.0", "Context-aware AI code review via %s" % self.llm_config["provider"],
            )
        self.registry.reload()
        self.chat_client = (
            JsonChatClient(
                str(self.llm_config["base_url"]), str(self.llm_config["api_key"]),
                str(self.llm_config["model"]), str(self.llm_config["provider"]),
                settings.timeout_seconds, dict(self.llm_config.get("headers") or {}),
            ) if self.llm_config else None
        )
        self.reviewer = self._build_agentic_reviewer()
        self.batch_review = BatchReview(self.store, self._batch_reviewer, settings.review_task_token_budget)
        self.harness = ReviewHarness(
            self.store, self.reviewer, settings.max_steps, settings.timeout_seconds,
            observability=self.observability,
        )
        self.github = GitHubClient(settings.github_token)
        self.workbench = ReviewWorkbench(self)
        self.github_review = GitHubReview(self)
        repair_verifier = RepairVerifier(
            settings.repair_test_command, settings.repair_verify_timeout_seconds
        )
        self.fixer = (
            VerifiedPatchFixer(self.chat_client, repair_verifier)
            if self.chat_client else SuggestionOnlyFixer()
        )
        self.auth = AuthManager(
            self.store, settings.auth_secret, settings.session_ttl_seconds,
            settings.bootstrap_admin_username, settings.bootstrap_admin_password,
            settings.default_tenant_id,
        )
        self.releases = ReleaseManager(self.store)
        self.alerts = AlertManager(
            self.store, settings.alert_failure_rate, settings.alert_min_samples
        )
        self.evolution = EvolutionEngine(
            self.store,
            reviewer_factory=self._build_llm_reviewer if self.llm_config else None,
            min_cases=settings.eval_min_cases,
            max_cases=settings.eval_max_cases,
            min_improvement=settings.eval_min_improvement,
            min_holdout_cases=settings.eval_min_holdout_cases,
            max_metric_regression=settings.eval_max_metric_regression,
            candidate_generator=(
                RootCauseEvolutionGenerator(self.chat_client)
                if self.chat_client else None
            ),
        )
        self.skill_evolution = SkillEvolutionEngine(
            self.store,
            reviewer_factory=(lambda artifact: AgentSkillReplayReviewer(
                    artifact, self.chat_client,
                    settings.agent_token_budget,
                    settings.agent_time_budget_seconds,
                )) if self.chat_client else None,
            min_cases=settings.eval_min_cases,
            max_cases=settings.eval_max_cases,
            min_improvement=settings.eval_min_improvement,
            min_holdout_cases=settings.eval_min_holdout_cases,
            max_metric_regression=settings.eval_max_metric_regression,
        )
        self.queue = TaskQueue(
            self._process_queued, settings.async_workers, settings.redis_url,
            settings.queue_max_attempts, settings.queue_lease_seconds,
            self._on_dead_letter,
        )
        if not settings.redis_url and self.chat_client is not None:
            self._recover_local_tasks()

    def _recover_local_tasks(self):
        pending = self.store.interrupted_tasks()
        if not pending:
            return

        def recover():
            for task_id in pending:
                with self.store.review_lock(task_id) as acquired:
                    if not acquired:
                        continue
                    task = self.store.get(task_id)
                    if not task or task["state"] not in {"PENDING", "PLANNING", "EXECUTING", "REVIEWING"}:
                        continue
                    payload = self._review_message(task)
                if not self.queue._stop.is_set():
                    self.queue.submit(payload, message_id=task_id)

        recover()
        # A crashed SQLite worker's last heartbeat may still be valid at startup.
        retry = Timer(31, recover)
        retry.daemon = True
        retry.start()

    @staticmethod
    def _review_message(task):
        return {"task_id": task["id"], "repository": task["repository"], "pull_request": task.get("pull_request"),
                "tenant_id": task["tenant_id"], "diff_url": task["input"].get("diff_url"),
                "job_type": task["input"].get("job_type"), **(task["input"].get("github") or {})}

    # 按已解析的模型配置和当前提示词创建模型审查器。
    def _build_llm_reviewer(self, prompt: str = "") -> OpenAICompatibleReviewer:
        if not self.llm_config:
            raise RuntimeError("no LLM provider is configured")
        return OpenAICompatibleReviewer(
            str(self.llm_config["base_url"]),
            str(self.llm_config["api_key"]),
            str(self.llm_config["model"]),
            self.settings.timeout_seconds,
            system_prompt=prompt,
            provider=str(self.llm_config["provider"]),
            extra_headers=dict(self.llm_config.get("headers") or {}),
        )

    # 加载启用角色、活动提示词及结构化参数，组装多 Agent 审查器。
    def _build_agentic_reviewer(self, prompt_version=None) -> AgenticReviewer:
        enabled = {
            item.strip() for item in self.settings.enabled_agents.split(",") if item.strip()
        }
        unknown = enabled.difference({
            "lead", "security", "correctness-reliability", "critic"
        })
        if unknown:
            raise ValueError("unsupported enabled Agent role(s): %s" % ", ".join(sorted(unknown)))
        active_prompt = prompt_version or self.store.get_active_skill_version("llm-review")
        structured_config = {}
        if active_prompt:
            run = next((
                item for item in self.store.list_evolution_runs(200)
                if int(item.get("candidate_version") or 0) == int(active_prompt["version"])
                and (item.get("metrics") or {}).get("structured_candidate")
            ), None)
            if run:
                structured_config = (
                    run["metrics"]["structured_candidate"].get("candidate") or {}
                )
        return AgenticReviewer(
            self.store, self.chat_client,
            self.settings.agent_token_budget,
            self.settings.agent_time_budget_seconds,
            self.settings.llm_input_cost_per_million,
            self.settings.llm_output_cost_per_million,
            enabled,
            [
                item for item in self.registry.reviewers()
                if not isinstance(item, OpenAICompatibleReviewer)
            ],
            None,
            self.settings.repair_test_command,
            active_prompt["prompt"] if active_prompt else "",
            structured_config,
            self.memory,
            self.context_manager,
            self._active_agent_skills,
        )

    # 把任务上下文交给工作流执行，统一同步和异步审查入口。
    def _run_review(
        self, task_id: str, repository: str, pull_request: Optional[int],
        diff: str, tenant_id: str,
    ):
        task = self.store.get(task_id, tenant_id)
        if task and task["input"].get("review_engine") == ENGINE:
            if task["state"] == "SUCCESS" and task.get("report"):
                return self.harness._report_from_dict(task["report"])
            if task["state"] in {"PAUSED_BUDGET", "CANCELLED"}:
                return None
            return self.batch_review.run(task, diff)
        return self.harness.run(task_id, repository, pull_request, diff, tenant_id)

    def _batch_reviewer(self, scoped_store, snapshot):
        client = self.chat_client
        if (getattr(client, "provider", None), getattr(client, "model", None), getattr(client, "base_url", None)) != (
            snapshot["provider"], snapshot["model"], snapshot["base_url"],
        ):
            raise ReviewConflict("The pinned model is unavailable. Restore its configuration and resume.")
        reviewer = copy(self.reviewer)
        reviewer.store = scoped_store
        reviewer.client = client
        reviewer.prompt_overlay = snapshot["prompt"]
        reviewer.structured_config = snapshot["structured"]
        reviewer.default_token_budget = snapshot["role_budget"]
        reviewer.enabled_roles = set(snapshot["roles"])
        reviewer.context_manager = ContextManager(**snapshot["context"])
        skills = [AgentSkill.from_artifact(item["artifact"], item["version"]) for item in snapshot["skills"]]
        reviewer.skill_provider = lambda _tenant_id: skills
        reviewer._summaries = {}
        # Whole-task memory is consolidated only after the full PR review.
        reviewer.persist_review_memory = False
        return reviewer

    def _save_review_snapshot(self, task_id, tenant_id, assignment, enabled_agents=None):
        if not self.settings.review_batching_enabled:
            return
        active = self.store.get_active_skill_version("llm-review")
        lane = assignment.get("deployment") or {}
        canaries = {}
        if assignment.get("lane") == "canary":
            candidate = next((version for version in self.store.list_skill_versions("llm-review")
                              if version["version"] == lane.get("candidate_version")), None)
            if candidate:
                active = candidate
                canaries["llm-review"] = active["version"]
        reviewer = self._build_agentic_reviewer(active)
        selected_roles = set(enabled_agents or reviewer.enabled_roles)
        sizes = [reviewer._token_budget(role) for role in selected_roles]
        context = reviewer.context_manager
        skills = {skill.name: skill for skill in self._active_agent_skills(tenant_id)}
        # Pin any configured Skill canary just as the Prompt canary is pinned.
        for name in sorted(skills.keys() | {
            run["skill_name"] for run in self.store.list_skill_evolution_runs(200, tenant_id)
        }):
            release = self.releases.assignment(tenant_id, name, task_id)
            if release["lane"] == "canary":
                number = release["deployment"]["candidate_version"]
                version = next((item for item in self.store.list_skill_artifact_versions(name, tenant_id)
                                if item["version"] == number), None)
                if version:
                    skills[name] = AgentSkill.from_artifact(version["artifact"], str(number))
                    canaries[name] = number
        client = self.chat_client
        snapshot = {
            "provider": getattr(client, "provider", None), "model": getattr(client, "model", None),
            "base_url": getattr(client, "base_url", None), "prompt": reviewer.prompt_overlay,
            "prompt_version": active["version"] if active else None,
            "structured": reviewer.structured_config, "roles": sorted(selected_roles),
            "role_budget": reviewer.default_token_budget,
            "task_budget": self.settings.review_task_token_budget,
            "context": {key: getattr(context, key) for key in (
                "context_window_tokens", "input_token_budget", "diff_token_budget", "observation_token_budget",
                "recent_observations", "map_chunk_tokens",
            )},
            "batch_tokens": max(128, min(context.diff_token_budget, context.input_token_budget // 4,
                                         context.context_window_tokens // 4, min(sizes) // 5, 1600)),
            "skill_versions": {name: item.version for name, item in skills.items()},
            "canaries": canaries,
            "skills": [{"version": item.version, "artifact": item.to_artifact()} for item in skills.values()],
        }
        self.store.save_checkpoint(task_id, SNAPSHOT, snapshot)
        self.store.save_checkpoint(task_id, "workbench-version-summary", {
            key: snapshot[key] for key in ("provider", "model", "prompt_version", "skill_versions")
        })

    # 重新加载 Skill 和活动提示词，并重建审查器与工作流以应用变更。
    def reload_skills(self) -> list:
        if self.llm_config:
            active = self.store.get_active_skill_version("llm-review")
            self.registry.register(
                "llm-review",
                self._build_llm_reviewer(active["prompt"] if active else ""),
                "1.0.0", "Context-aware AI code review via %s" % self.llm_config["provider"],
            )
        self.registry.reload()
        skills = self.registry.list()
        self.reviewer = self._build_agentic_reviewer()
        self.harness = ReviewHarness(
            self.store, self.reviewer, self.settings.max_steps, self.settings.timeout_seconds,
            observability=self.observability,
        )
        return skills

    # 合并磁盘 Skill 与当前租户的活动制品，同名数据库版本覆盖磁盘版本。
    def _active_agent_skills(self, tenant_id: str) -> list:
        values = {skill.name: skill for skill in self.registry.agent_skills()}
        for version in self.store.list_active_skill_artifacts(tenant_id):
            artifact = validate_artifact(version["artifact"], version["skill_name"])
            values[version["skill_name"]] = AgentSkill.from_artifact(
                artifact, str(version["version"])
            )
        return [values[name] for name in sorted(values)]

    # 汇总扫描器和当前租户的 Agent Skill，输出管理界面需要的元数据。
    def list_skills(self, tenant_id: str) -> list:
        scanners = [item for item in self.registry.list() if item.get("kind") == "scanner"]
        return scanners + [{
            "name": skill.name, "version": skill.version,
            "description": skill.description, "source": skill.source,
            "kind": "agent-skill", "sandboxed": False,
            "permissions": list(skill.allowed_tools),
            "content_sha256": skill.content_sha256,
            "resources": list(skill.resource_paths),
        } for skill in self._active_agent_skills(tenant_id)]

    def _version_scope(self, kind, name, tenant_id):
        if kind not in {"prompt", "skill"} or not SKILL_NAME.fullmatch(name):
            raise ValueError("invalid version type or name")
        if kind == "prompt" and tenant_id != self.settings.default_tenant_id:
            raise PermissionError("Only the default tenant can manage the shared Prompt")
        if kind == "prompt" and name != "llm-review":
            raise ValueError("llm-review is the supported Prompt profile")

    def version_catalog(self, kind, name, tenant_id):
        self._version_scope(kind, name, tenant_id)
        if kind == "prompt":
            versions = self.store.list_skill_versions(name)
            runs = self.store.list_evolution_runs(1000)
            status = self.evolution.status()
        else:
            versions = self.store.list_skill_artifact_versions(name, tenant_id)
            runs = self.store.list_skill_evolution_runs(1000, tenant_id)
            status = self.skill_evolution.status(name, tenant_id)
        by_version = {run.get("candidate_version"): run for run in reversed(runs) if run["skill_name"] == name}
        history = self.store.stable_release_history(tenant_id, kind, name)
        stable = next((version["version"] for version in versions if version["active"]), None)
        deployment = self.store.get_deployment(tenant_id, name)
        results = []
        for version in versions:
            number = version["version"]
            run = by_version.get(number) or {}
            released = number in history or run.get("decision") == "activated"
            passed = run.get("decision") in {"ready", "shadow_ready", "activated"}
            outdated = bool(passed and not version["active"] and not released and run.get("baseline_version") != stable)
            state = ("active" if version["active"] else "canary" if deployment and deployment["status"] == "running"
                     and deployment["candidate_version"] == number else "stale" if outdated else "historical" if released
                     else "ready" if passed else run.get("decision", "unevaluated"))
            results.append({**version, "evaluation": run or None, "publishable": released or passed and not outdated,
                            "release_state": state, "previously_released": released, "baseline_changed": outdated})
        return {
            "versions": results, "deployment": deployment, "status": status, "stable_version": stable,
        }

    def version_detail(self, kind, name, number, tenant):
        from difflib import unified_diff
        from .evolution import DEFAULT_PROMPT

        catalog = self.version_catalog(kind, name, tenant)
        versions = {item["version"]: item for item in catalog["versions"]}
        selected = versions.get(number)
        if not selected:
            raise LookupError("Version not found")
        run = selected.get("evaluation") or {}
        baseline = versions.get(run.get("baseline_version"))
        if kind == "prompt":
            before, after = baseline["prompt"] if baseline else DEFAULT_PROMPT, selected["prompt"]
        else:
            before = (baseline["artifact"] if baseline else self.skill_evolution.empty_artifact(name))["files"]["SKILL.md"]
            after = selected["artifact"]["files"]["SKILL.md"]
        metrics_data = run.get("metrics") or {}
        return {"version": selected, "baseline_text": before, "candidate_text": after,
                "changes": "\n".join(unified_diff(before.splitlines(), after.splitlines(),
                                     fromfile="baseline", tofile="candidate", lineterm="")),
                "feedback": self.store.workbench_feedback(tenant, metrics_data.get("feedback_ids") or []),
                "model": self.store.evaluation_model_for_version(tenant, kind, name, number),
                "deployment": catalog["deployment"], "stable_version": catalog["stable_version"]}

    def publish_version(self, kind, name, version, tenant_id, actor, canary_percent=0):
        self._version_scope(kind, name, tenant_id)
        if type(canary_percent) is not int or not 0 <= canary_percent <= 100:
            raise ValueError("canary_percent must be an integer between 0 and 100")
        with self.store.review_lock(f"versions:{tenant_id}:{name}") as locked:
            if not locked:
                raise ReviewConflict("Another version operation is running")
            catalog = self.version_catalog(kind, name, tenant_id)
            selected = next((item for item in catalog["versions"] if item["version"] == version), None)
            if selected and selected["baseline_changed"]:
                raise ReviewConflict("Stable version changed since evaluation. Re-evaluate before publishing.")
            if not selected or not (selected["publishable"] or selected["active"]):
                raise ReviewConflict("Only versions that passed evaluation can be published")
            previous = next((item["version"] for item in catalog["versions"] if item["active"]), None)
            if canary_percent:
                if version == previous:
                    raise ReviewConflict("The current stable version is already active")
                deployment = self.releases.configure(tenant_id, name, {
                    "stable_version": previous, "candidate_version": version, "canary_percent": canary_percent,
                })
                result = {"version": version, "decision": "canary", "deployment": deployment}
            else:
                activate = (lambda: self.evolution.rollback(name, version)) if kind == "prompt" else (
                    lambda: self.skill_evolution.rollback(name, version, tenant_id)
                )
                if not activate():
                    raise ReviewConflict("Could not activate this version")
                deployment = catalog["deployment"]
                if deployment and deployment["status"] == "running":
                    self.store.save_deployment(tenant_id, name, {**deployment, "status": "stopped",
                                                                "canary_percent": 0, "shadow_percent": 0})
                self.reload_skills()
                feedback = ((selected.get("evaluation") or {}).get("metrics") or {}).get("feedback_ids", [])
                if feedback:
                    self.store.resolve_failure_cases(feedback)
                result = {"version": version, "decision": "activated", "previous_version": previous}
            self.store.audit(tenant_id, actor, f"{kind}.publish", name, result)
            return result

    def _observe_review_release(self, task, failed):
        tenant = task["tenant_id"]
        if task["input"].get("review_engine") != ENGINE:
            self.releases.observe(tenant, "llm-review", failed, task["input"].get("release_lane", "stable"))
            return
        saved = self.store.load_checkpoints(task["id"])
        for name, version in checkpoint(saved, SNAPSHOT).get("canaries", {}).items():
            checkpoint_name = "release-observed:" + name
            if checkpoint(saved, checkpoint_name):
                continue
            deployment = self.store.get_deployment(tenant, name)
            if deployment and deployment["status"] == "running" and deployment["candidate_version"] == version:
                self.releases.observe(tenant, name, failed, "canary")
                self.store.save_checkpoint(task["id"], checkpoint_name, {"version": version})

    def evaluate_version(self, kind, name, tenant_id, options):
        self._version_scope(kind, name, tenant_id)
        automatic = options.get("automatic", False)
        if kind == "prompt":
            if automatic:
                return self.evolution.auto_propose(name, tenant_id, activation_policy="manual")
            return self.evolution.propose(name, options.get("prompt", ""), activation_policy="manual")
        if automatic:
            return self.skill_evolution.auto_propose(name, tenant_id, manual=True)
        return self.skill_evolution.propose(name, options.get("artifact"), tenant_id, manual=True)

    def queue_evolution(self, kind, name, tenant_id, actor, options):
        self._version_scope(kind, name, tenant_id)
        job_id = str(uuid.uuid4())
        model = {key: self.llm_config.get(key) for key in ("provider", "model")}
        self.store.create(job_id, "evolution/" + kind, None,
                          {"job_type": "evolution", "kind": kind, "name": name, "evaluation_model": model}, tenant_id)
        self.store.save_checkpoint(job_id, "evolution-input", options)
        self.store.audit(tenant_id, actor, f"{kind}.evaluate", name, {"job_id": job_id})
        self.queue.submit({"task_id": job_id, "job_type": "evolution", "tenant_id": tenant_id}, message_id=job_id)
        return {"job_id": job_id, "state": "PENDING"}

    def _process_evolution_job(self, payload):
        job_id = payload["task_id"]
        tenant = payload["tenant_id"]
        with self.store.review_lock(job_id) as locked:
            if not locked and self.settings.redis_url:
                raise QueueLeaseBusy()
            job = self.store.get(job_id, tenant)
            if not locked or not job or job["state"] in {"SUCCESS", "FAILED", "CANCELLED"}:
                return
            saved = self.store.load_checkpoints(job_id)
            result = checkpoint(saved, "evolution-result")
            if job["state"] == "EXECUTING" and not result:
                self.store.fail(job_id, "Evaluation was interrupted. Submit it again.", self.batch_review._event(
                    job, TaskState.FAILED, "Evaluation interrupted"))
                return
            self.store.transition(job_id, self.batch_review._event(job, TaskState.EXECUTING, "Evaluating candidate"))
            try:
                if not result:
                    model = job["input"].get("evaluation_model")
                    if model and model != {key: self.llm_config.get(key) for key in ("provider", "model")}:
                        raise ReviewConflict("Evaluation model changed while queued. Submit it again.")
                    result = self.evaluate_version(job["input"]["kind"], job["input"]["name"], tenant,
                                                   checkpoint(saved, "evolution-input"))
                    self.store.save_checkpoint(job_id, "evolution-result", result)
                self.store.transition(job_id, self.batch_review._event(job, TaskState.SUCCESS, "Evaluation completed"))
            except Exception as exc:
                self.store.fail(job_id, str(exc), self.batch_review._event(job, TaskState.FAILED, "Evaluation failed"))

    def evolution_job(self, job_id, tenant_id):
        job = self.store.get(job_id, tenant_id)
        if not job or job["input"].get("job_type") != "evolution":
            return None
        saved = self.store.load_checkpoints(job_id)
        return {"job_id": job_id, "state": job["state"], "error": job["error"],
                "model": job["input"].get("evaluation_model"),
                "result": checkpoint(saved, "evolution-result") or None}

    # 检查仓库名及 Diff 的 UTF-8 字节数，拒绝空输入或超大请求。
    def _validate_review(self, repository: str, diff: str) -> None:
        if not repository or len(repository) > 250:
            raise ValueError("repository is required and must be at most 250 characters")
        size = len(diff.encode("utf-8"))
        if size == 0:
            raise ValueError("diff is required")
        if size > self.settings.max_diff_bytes:
            raise ValueError("diff exceeds maximum size of %d bytes" % self.settings.max_diff_bytes)

    # 在创建审查任务前确认已配置模型，避免任务进入无法执行的队列。
    def _require_agentic_model(self) -> None:
        if self.chat_client is None:
            raise RuntimeError("agentic review requires a configured model")

    # 生成任务标识，记录 Diff 指纹与发布分组，并单独持久化原始 Diff。
    def _create_task(
        self, repository: str, diff: str, pull_request: Optional[int], source: str,
        tenant_id: str = "default", repository_root: str = "",
        enabled_agents: Optional[list] = None,
        enabled_skills: Optional[list] = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        encoded = diff.encode("utf-8")
        assignment = self.releases.assignment(tenant_id, "llm-review", task_id)
        self.store.create(task_id, repository, pull_request, {
            "source": source, "diff_bytes": len(encoded), "diff_sha256": hashlib.sha256(encoded).hexdigest(),
            "release_lane": assignment["lane"], "shadow": assignment["shadow"],
            "mode": RunMode.AGENTIC.value,
            "initial_token_budget": self.settings.review_task_token_budget,
            "repository_root": repository_root,
            "enabled_agents": enabled_agents or [],
            "enabled_skills": enabled_skills or [],
            **({"review_engine": ENGINE} if self.settings.review_batching_enabled else {}),
        }, tenant_id)
        # 队列只携带任务标识和路由信息；完整 Diff 保存在存储中，重启后仍可读取。
        self.store.save_task_payload(task_id, diff)
        self._save_review_snapshot(task_id, tenant_id, assignment, enabled_agents)
        return task_id

    # 先创建待拉取 Diff 的任务记录，供 Webhook 快速入队后再下载变更。
    def _create_deferred_task(
        self, repository: str, pull_request: Optional[int], source: str,
        tenant_id: str, payload: Dict[str, Any],
    ) -> str:
        task_id = str(uuid.uuid4())
        assignment = self.releases.assignment(tenant_id, "llm-review", task_id)
        self.store.create(task_id, repository, pull_request, {
            "source": source, "diff_pending": True,
            "release_lane": assignment["lane"], "shadow": assignment["shadow"],
            **payload,
            "mode": RunMode.AGENTIC.value,
            "initial_token_budget": self.settings.review_task_token_budget,
            **({"review_engine": ENGINE} if self.settings.review_batching_enabled else {}),
        }, tenant_id)
        self._save_review_snapshot(task_id, tenant_id, assignment)
        return task_id

    # 校验输入和仓库授权后同步执行审查，并记录发布结果与失败告警。
    def create_review(
        self, repository: str, diff: str, pull_request: Optional[int] = None,
        source: str = "api", tenant_id: str = "default", mode: str = "",
        repository_root: str = "", enabled_agents: Optional[list] = None,
        enabled_skills: Optional[list] = None,
    ) -> Dict[str, Any]:
        self._validate_review(repository, diff)
        RunMode.parse(mode) if mode else None
        self._require_agentic_model()
        self._validate_repository_root(repository_root)
        self._validate_enabled_agents(enabled_agents)
        self._validate_enabled_skills(enabled_skills, tenant_id)
        self._authorize_repository(tenant_id, repository)
        task_id = self._create_task(
            repository, diff, pull_request, source, tenant_id,
            repository_root, enabled_agents, enabled_skills,
        )
        try:
            with self.observability.span(
                "review", task_id, task_id=task_id, tenant_id=tenant_id,
                repository=repository,
            ), metrics.timer("review_duration"):
                with self.store.review_lock(task_id) as acquired:
                    if not acquired:
                        raise ReviewConflict("Task is already running")
                    report = self._run_review(task_id, repository, pull_request, diff, tenant_id)
            if report is None:
                return {"task_id": task_id, "state": self.store.get(task_id, tenant_id)["state"]}
            metrics.inc("reviews_total")
            self._observe_review_release(self.store.get(task_id, tenant_id), False)
            return {"task_id": task_id, "state": "SUCCESS", "report": report.to_dict()}
        except Exception:
            task = self.store.get(task_id, tenant_id) or {}
            if task:
                self._observe_review_release(task, True)
            self.alerts.evaluate(tenant_id)
            raise

    # 完成与同步入口相同的校验，再保存任务并投递队列，返回待执行状态。
    def enqueue_review(
        self, repository: str, diff: str, pull_request: Optional[int] = None,
        source: str = "api", github_issue_url: str = "", installation_id: Optional[int] = None,
        tenant_id: str = "default", mode: str = "", repository_root: str = "",
        enabled_agents: Optional[list] = None,
        enabled_skills: Optional[list] = None,
    ) -> Dict[str, Any]:
        self._validate_review(repository, diff)
        RunMode.parse(mode) if mode else None
        self._require_agentic_model()
        self._validate_repository_root(repository_root)
        self._validate_enabled_agents(enabled_agents)
        self._validate_enabled_skills(enabled_skills, tenant_id)
        self._authorize_repository(tenant_id, repository)
        task_id = self._create_task(
            repository, diff, pull_request, source, tenant_id,
            repository_root, enabled_agents, enabled_skills,
        )
        self.queue.submit({
            "task_id": task_id, "repository": repository, "pull_request": pull_request,
            "github_issue_url": github_issue_url, "installation_id": installation_id,
            "tenant_id": tenant_id,
        }, message_id=task_id)
        metrics.inc("reviews_enqueued_total")
        return {"task_id": task_id, "state": "PENDING", "queue": self.queue.backend}

    # 读取任务 Diff，必要时从 GitHub 拉取，再执行审查并按配置回写报告评论。
    def _process_queued(self, payload: Dict[str, Any]) -> None:
        if payload.get("job_type") == "evolution":
            self._process_evolution_job(payload)
            return
        with self.store.review_lock(payload["task_id"]) as acquired:
            if acquired:
                self._process_review_delivery(payload)
            elif self.settings.redis_url:
                raise QueueLeaseBusy()

    def _process_review_delivery(self, payload: Dict[str, Any]) -> None:
        task_id = payload["task_id"]
        task = self.store.get(task_id)
        if not task:
            raise PermanentTaskError("task record no longer exists")
        tenant_id = payload.get("tenant_id") or task.get("tenant_id") or "default"
        if task["state"] in {"PAUSED_BUDGET", "CANCELLED"}:
            return
        diff = self.store.get_task_payload(task_id)
        # Webhook 先入队再下载 Diff，使接收请求不必等待远程仓库访问。
        if diff is None and payload.get("diff_url"):
            client = (
                self.github_client_for_installation(payload.get("installation_id"))
                if payload.get("installation_id") else self.github
            )
            client.ensure_repository_access(payload["repository"])
            expected = task["input"].get("head_sha")
            try:
                if expected:
                    self._check_review_commit(client, task)
                diff = client.fetch_diff(payload["diff_url"])
                if expected:
                    self._check_review_commit(client, task)
            except PermanentTaskError:
                self.store.save_checkpoint(task_id, "workbench-pr-stale", {"updated_at": utc_now()})
                raise
            self._validate_review(payload["repository"], diff)
            encoded = diff.encode("utf-8")
            self.store.save_task_payload(task_id, diff)
            self.store.update_task_input(task_id, {
                "diff_pending": False, "diff_bytes": len(encoded),
                "diff_sha256": hashlib.sha256(encoded).hexdigest(),
            })
        if diff is None:
            raise PermanentTaskError("task payload no longer exists")
        try:
            with self.observability.span(
                "review.async", task_id, task_id=task_id, tenant_id=tenant_id,
            ), metrics.timer("review_duration"):
                report = self._run_review(
                    task_id, payload["repository"], payload.get("pull_request"), diff,
                    tenant_id,
                )
            if report is None:
                return
            if task["state"] != "SUCCESS":
                metrics.inc("reviews_total")
            if task["state"] != "SUCCESS" or task["input"].get("review_engine") == ENGINE:
                self._observe_review_release(task, False)
            self.github_review.publish(task, report, payload)
        except Exception as exc:
            metrics.inc("reviews_failed_total")
            if task["input"].get("review_engine") != ENGINE and task["state"] != "SUCCESS":
                self._observe_review_release(task, True)
            self.alerts.evaluate(tenant_id)
            if task["input"].get("review_engine") == ENGINE and isinstance(exc, (ValueError, ModelResponseError, RuntimeBudgetExceeded)):
                raise PermanentTaskError(str(exc)) from exc
            raise

    # 把尚未结束的任务标记为失败，并创建死信告警，防止任务一直显示运行中。
    def _on_dead_letter(self, payload: Dict[str, Any], error: str) -> None:
        task_id = payload.get("task_id", "")
        tenant_id = payload.get("tenant_id", "default")
        task = self.store.get(task_id, tenant_id) if task_id else None
        if task and task.get("state") not in {
            TaskState.SUCCESS.value, TaskState.FAILED.value, TaskState.CANCELLED.value, TaskState.PAUSED_BUDGET.value,
        }:
            step = max(
                [int(item.get("step", 0)) for item in task.get("trace", [])] or [0]
            ) + 1
            self.store.fail(
                task_id, error,
                TraceEvent(
                    step, TaskState.FAILED,
                    "Task entered the dead-letter queue: %s" % error, utc_now(),
                ),
            )
        if task and task["input"].get("review_engine") == ENGINE and task["state"] not in {
            "SUCCESS", "CANCELLED", "PAUSED_BUDGET",
        }:
            self._observe_review_release(task, True)
        self.store.create_alert(
            tenant_id, "dlq:%s" % (task_id or "unknown"), "critical",
            "Task %s entered the dead-letter queue: %s" % (task_id, error),
        )
        metrics.inc("dead_letters_total")

    # 按 delivery ID 去重，只对支持的 PR 事件创建延迟拉取 Diff 的异步任务。
    def handle_github_pull_request(
        self, payload: Dict[str, Any], delivery_id: str,
        payload_sha256: str, tenant_id: str = "",
    ) -> Dict[str, Any]:
        installation_id = (payload.get("installation") or {}).get("id")
        tenant_id = tenant_id or (
            self.store.installation_tenant(installation_id) if installation_id else None
        ) or self.settings.default_tenant_id
        # 先占用 delivery ID，并核对载荷指纹，避免重复投递创建多个任务。
        if not self.store.claim_webhook(
            delivery_id, tenant_id, "pull_request", payload_sha256
        ):
            existing = self.store.get_webhook(delivery_id) or {}
            return {
                "duplicate": True, "task_id": existing.get("task_id"),
                "state": "PENDING" if existing.get("task_id") else "ACCEPTED",
            }
        action = payload.get("action")
        if action not in {"opened", "reopened", "synchronize"}:
            self.store.complete_webhook(delivery_id, None)
            return {"ignored": True, "reason": "unsupported pull_request action: %s" % action}
        self._require_agentic_model()
        pull = payload.get("pull_request") or {}
        repository = (payload.get("repository") or {}).get("full_name", "")
        number = payload.get("number")
        diff_url = pull.get("diff_url")
        if not repository or not isinstance(number, int) or not diff_url:
            raise ValueError("invalid GitHub pull_request payload")
        self._authorize_repository(tenant_id, repository)
        try:
            result = self.github_review.enqueue(repository, number, pull, tenant_id, installation_id, "github-webhook")
        except Exception:
            self.store.release_unassigned_webhook(delivery_id, tenant_id)
            raise
        self.store.complete_webhook(delivery_id, result["task_id"])
        return result

    @staticmethod
    def _check_review_commit(client, task):
        live = client.get_pull_request(task["repository"], task["pull_request"])
        for side in ("head", "base"):
            sha = task["input"].get(f"{side}_sha")
            if sha and (live.get(side) or {}).get("sha") != sha:
                raise PermanentTaskError("The GitHub PR moved to a different commit")

    # 无安装标识时使用常规客户端，否则获取对应 GitHub App 安装令牌。
    def github_client_for_installation(self, installation_id: Optional[int] = None) -> GitHubClient:
        if installation_id is None:
            return self.github
        if not self.settings.github_app_id or not self.settings.github_private_key_path:
            raise ValueError("GitHub App credentials are not configured")
        token = GitHubAppAuthenticator(
            self.settings.github_app_id, self.settings.github_private_key_path
        ).installation_token(installation_id)
        return GitHubClient(token)

    # 确认已有审查报告且仓库允许自动修复，再调用修复器创建变更。
    def create_fix(
        self, task_id: str, installation_id: Optional[int] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        task = self.store.get(task_id, tenant_id)
        if not task or not task.get("report"):
            raise ValueError("completed task not found")
        if task.get("pull_request") is None:
            raise ValueError("fix commits require a GitHub pull request task")
        actual_tenant = task.get("tenant_id") or tenant_id or "default"
        if not self.store.repository_allowed(actual_tenant, task["repository"], True):
            raise PermissionError("automatic repair is not enabled for this repository")
        report = {**task["report"], "findings": [item for item in task["report"].get("findings", [])
                                                  if item.get("line_side", "new") == "new"]}
        client = self.github_client_for_installation(installation_id or (task["input"].get("github") or {}).get("installation_id"))
        if task["input"].get("head_sha"):
            try:
                self._check_review_commit(client, task)
            except PermanentTaskError as exc:
                raise ReviewConflict(str(exc)) from exc
        result = self.fixer.create_fix_commits(client, task["repository"], task["pull_request"], report)
        self.store.save_checkpoint(task_id, "workbench-fix", result)
        metrics.inc("fix_runs_total")
        return result

    # 仅为已完成的审查保存合法反馈，同时写入案例库与仓库隔离的记忆。
    def record_feedback(
        self, task_id: str, category: str, finding: Optional[dict], note: str,
        tenant_id: Optional[str] = None, skill_name: str = "llm-review",
    ) -> dict:
        task = self.store.get(task_id, tenant_id)
        if not task:
            raise ValueError("task not found")
        self._authorize_repository(task["tenant_id"], task["repository"])
        # 反馈必须对应已完成的报告，防止把运行中或失败任务当作审查学习样本。
        if task.get("state") != "SUCCESS" or not task.get("report"):
            raise ValueError("feedback requires a completed review task")
        if category not in {"false_positive", "missed_issue", "bad_fix", "accepted"}:
            raise ValueError("unsupported feedback category")
        skill_name = str(skill_name or "llm-review").strip().lower()
        if not SKILL_NAME.fullmatch(skill_name):
            raise ValueError("invalid feedback skill_name")
        task_skills = {
            str(value).strip().lower()
            for value in (task.get("input") or {}).get("enabled_skills") or []
            if str(value).strip()
        }
        task_skills.update(
            str(value).strip().lower()
            for value in ((task.get("report") or {}).get("collaboration") or {}).get(
                "agent_skills", []
            )
            if str(value).strip()
        )
        if skill_name != "llm-review" and skill_name not in task_skills:
            raise ValueError("feedback skill_name was not used by this review task")
        self.store.record_failure_case(
            task_id, category, {"finding": finding, "note": note[:2000]}, skill_name,
        )
        self.memory.remember_feedback(
            task.get("tenant_id") or tenant_id or "default", task["repository"],
            task_id, category, finding, note[:2000],
        )
        metrics.inc("feedback_total")
        return {"recorded": True, "category": category, "skill_name": skill_name}

    # 已成功的任务直接返回报告；其余任务读取已保存的 Diff 并重新入队。
    def resume_task(self, task_id: str, tenant_id: Optional[str] = None, additional_tokens=0) -> dict:
        task = self.store.get(task_id, tenant_id)
        if not task:
            raise ValueError("task not found")
        self._authorize_repository(task["tenant_id"], task["repository"])
        if task["input"].get("review_engine") == ENGINE:
            if type(additional_tokens) is not int or not 0 <= additional_tokens <= 1000000:
                raise ValueError("additional_tokens must be an integer between 0 and 1000000")
            with self.store.review_lock(task_id) as acquired:
                task = self.store.get(task_id, tenant_id)
                if not acquired or task["state"] not in {"PAUSED_BUDGET", "FAILED"} or task["cancel_requested"]:
                    raise ReviewConflict("Only paused or failed reviews can be resumed")
                if task["state"] == "PAUSED_BUDGET" and not additional_tokens:
                    raise ValueError("additional_tokens is required to resume a budget-paused review")
                total = int(task["input"].get("additional_budget_tokens", 0)) + additional_tokens
                self.store.update_task_input(task_id, {"additional_budget_tokens": total})
                self.store.transition(task_id, self.batch_review._event(task, TaskState.PENDING, "Resume queued"))
            self.queue.submit(self._review_message(task), message_id=task_id)
            return {"task_id": task_id, "state": "PENDING", "resumed": True}
        if task["state"] == "SUCCESS":
            return {"task_id": task_id, "state": "SUCCESS", "report": task["report"]}
        diff = self.store.get_task_payload(task_id)
        if diff is None:
            raise ValueError("task payload is no longer available")
        self.queue.submit({
            "task_id": task_id, "repository": task["repository"],
            "pull_request": task.get("pull_request"),
            "tenant_id": task.get("tenant_id", "default"),
        }, message_id=task_id)
        return {"task_id": task_id, "state": "PENDING", "resumed": True}

    # 写入取消请求，由运行时在执行边界检查并结束任务。
    def cancel_task(self, task_id: str, tenant_id: Optional[str] = None) -> bool:
        task = self.store.get(task_id, tenant_id)
        if not task:
            return False
        self._authorize_repository(task["tenant_id"], task["repository"])
        if task["state"] in {"SUCCESS", "FAILED", "CANCELLED"}:
            raise ReviewConflict("The task has already finished")
        requested = self.store.request_cancel(task_id, tenant_id)
        if requested:
            task = self.store.get(task_id, tenant_id)
            if task["state"] == "PAUSED_BUDGET":
                self.store.cancel(task_id, self.batch_review._event(task, TaskState.CANCELLED, "Review cancelled"))
        return requested

    def accept_review(self, task_id, tenant_id, actor, revision):
        task = self.store.get(task_id, tenant_id)
        if not task:
            raise ValueError("task not found")
        self._authorize_repository(tenant_id, task["repository"])
        with self.store.review_lock(task_id) as acquired:
            if not acquired:
                raise ReviewConflict("The review is still running")
            task = self.batch_review.details(self.store.get(task_id, tenant_id), True)
            if not revision or revision != task.get("report_revision"):
                raise ReviewConflict("Open the latest completed report before confirming")
            if task.get("confirmation"):
                return task["confirmation"]
            if not task.get("actions", {}).get("accept"):
                raise ReviewConflict("Only completed reports with full text coverage can be confirmed")
            confirmation = {"report_revision": revision, "actor": actor, "accepted_at": utc_now()}
            self.store.save_checkpoint(task_id, "review-v2-confirmation", confirmation)
            self.store.audit(tenant_id, actor, "review.accept", task_id, {"report_revision": revision})
            return confirmation

    # 检查当前租户是否被允许审查目标仓库。
    def _authorize_repository(self, tenant_id: str, repository: str) -> None:
        if not self.store.repository_allowed(tenant_id, repository):
            raise PermissionError("repository is not authorized for this tenant")

    # 要求本地仓库根路径为已存在的绝对目录，空值表示仅使用 Diff。
    @staticmethod
    def _validate_repository_root(repository_root: str) -> None:
        if not repository_root:
            return
        import os
        if not os.path.isabs(repository_root) or not os.path.isdir(repository_root):
            raise ValueError("repository_root must be an existing absolute directory")

    # 限制请求中的角色名称，拒绝不支持的 Agent。
    @staticmethod
    def _validate_enabled_agents(enabled_agents: Optional[list]) -> None:
        if enabled_agents is None:
            return
        allowed = {"lead", "security", "correctness-reliability", "critic"}
        unknown = set(enabled_agents).difference(allowed)
        if unknown:
            raise ValueError("unsupported enabled Agent role(s): %s" % ", ".join(sorted(unknown)))

    # 检查 Skill 名称类型及当前租户可见范围，拒绝未知技能。
    def _validate_enabled_skills(
        self, enabled_skills: Optional[list], tenant_id: str,
    ) -> None:
        if enabled_skills is None:
            return
        if not all(isinstance(item, str) for item in enabled_skills):
            raise ValueError("enabled_skills must contain Agent Skill names")
        available = {skill.name for skill in self._active_agent_skills(tenant_id)}
        unknown = set(enabled_skills).difference(available)
        if unknown:
            raise ValueError(
                "unknown enabled Agent Skill(s): %s" % ", ".join(sorted(unknown))
            )
