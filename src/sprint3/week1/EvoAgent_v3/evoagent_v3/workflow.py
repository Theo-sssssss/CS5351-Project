from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from .diff_parser import parse_unified_diff
from .gates import validate_findings
from .llm import LLMResult
from .models import normalize_report
from .prompts import (
    AGENTIC_CORRECTNESS_MISSION,
    AGENTIC_CRITIC_MISSION,
    AGENTIC_LEAD_MISSION,
    AGENTIC_SECURITY_MISSION,
    BASELINE,
    CORRECTNESS,
    CRITIC,
    LEAD_PLAN,
    SECURITY,
    SYNTHESIS,
)
from .repository_tools import RepositoryToolSuite
from .runtime import AgentRuntime, AgentTool, RuntimeBudget, RuntimeLedger, ToolRegistry


class LLMProtocol(Protocol):
    model: str

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMResult: ...


class WorkflowEngine:
    def __init__(self, llm: LLMProtocol, store=None, runtime_budget: RuntimeBudget | None = None):
        self.llm = llm
        self.store = store
        self.runtime_budget = runtime_budget or RuntimeBudget()

    def review(self, task_id: str, repository: str, number: int, diff: str, mode: str) -> tuple[dict, dict]:
        if mode == "baseline":
            return self._baseline(task_id, repository, number, diff)
        if mode == "collaborative":
            return self._collaborative(task_id, repository, number, diff)
        if mode == "agentic":
            return self._agentic(task_id, repository, number, diff)
        raise ValueError("mode must be baseline, collaborative, or agentic")

    def _call(self, task_id: str, role: str, phase: int, prompt: str, user: str) -> tuple[dict, dict]:
        digest = hashlib.sha256(user.encode("utf-8")).hexdigest()
        run_id = self.store.start_role(task_id, role, phase, self.llm.model, digest) if self.store else 0
        started = time.monotonic()
        try:
            result = self.llm.complete_json(prompt, user)
            latency_ms = max(0, round((time.monotonic() - started) * 1000))
            if self.store:
                self.store.finish_role(run_id, result.value, latency_ms, result.input_tokens, result.output_tokens)
            value = result.value
            if value.get("action") == "final" and isinstance(value.get("result"), dict):
                value = value["result"]
            return value, {
                "role": role,
                "latency_ms": latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }
        except Exception as exc:
            latency_ms = max(0, round((time.monotonic() - started) * 1000))
            if self.store:
                self.store.fail_role(run_id, str(exc), latency_ms)
            raise

    @staticmethod
    def _user(diff: str, extra: dict | None = None) -> str:
        prefix = ""
        if extra is not None:
            prefix = "Context JSON:\n" + json.dumps(extra, ensure_ascii=False) + "\n\n"
        return prefix + "Unified diff:\n" + diff

    @staticmethod
    def _metrics(calls: list[dict], gate_rejected: int) -> dict:
        return {
            "call_count": len(calls),
            "input_tokens": sum(call["input_tokens"] for call in calls),
            "output_tokens": sum(call["output_tokens"] for call in calls),
            "model_latency_ms": sum(call["latency_ms"] for call in calls),
            "gate_rejected": gate_rejected,
            "roles": [call["role"] for call in calls],
        }

    def _baseline(self, task_id: str, repository: str, number: int, diff: str) -> tuple[dict, dict]:
        raw, call = self._call(task_id, "baseline", 1, BASELINE, self._user(diff))
        parsed = parse_unified_diff(diff)
        gate = validate_findings(raw.get("findings") or [], parsed, "baseline")
        report = normalize_report(raw, repository, number, "baseline", gate.accepted)
        report["gate_rejections"] = gate.rejected
        return report, self._metrics([call], len(gate.rejected))

    def _collaborative(self, task_id: str, repository: str, number: int, diff: str) -> tuple[dict, dict]:
        calls: list[dict] = []
        plan, call = self._call(task_id, "lead", 1, LEAD_PLAN, self._user(diff))
        calls.append(call)

        def worker(role: str, prompt: str, focus_key: str) -> tuple[dict, dict]:
            context = {"lead_plan": plan, "assigned_focus": plan.get(focus_key, [])}
            return self._call(task_id, role, 2, prompt, self._user(diff, context))

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="v3-specialist") as pool:
            security_future = pool.submit(worker, "security", SECURITY, "security_focus")
            correctness_future = pool.submit(worker, "correctness_reliability", CORRECTNESS, "correctness_focus")
            security_raw, security_call = security_future.result()
            correctness_raw, correctness_call = correctness_future.result()
        calls.extend([security_call, correctness_call])

        candidates = []
        for role, raw in (("security", security_raw), ("correctness_reliability", correctness_raw)):
            for finding in raw.get("findings") or []:
                if isinstance(finding, dict):
                    value = dict(finding)
                    previous = value.get("reported_by")
                    if not isinstance(previous, list):
                        previous = [str(previous)] if previous else []
                    value["reported_by"] = sorted(set(previous + [role]))
                    candidates.append(value)
        critic_context = {"lead_plan": plan, "candidate_findings": candidates}
        critic, critic_call = self._call(task_id, "critic", 3, CRITIC, self._user(diff, critic_context))
        calls.append(critic_call)

        synthesis_context = {
            "lead_plan": plan,
            "critic_summary": critic.get("summary", ""),
            "approved_findings": critic.get("findings") or [],
        }
        final_raw, synthesis_call = self._call(
            task_id, "lead_synthesis", 4, SYNTHESIS, json.dumps(synthesis_context, ensure_ascii=False)
        )
        calls.append(synthesis_call)
        parsed = parse_unified_diff(diff)
        # Synthesis may summarize, but cannot rewrite or drop Critic-approved evidence.
        gate = validate_findings(critic.get("findings") or [], parsed, "critic")
        for accepted in gate.accepted:
            reporters = set(accepted.get("reported_by") or [])
            for candidate in candidates:
                same_rule = accepted.get("rule_id") and accepted.get("rule_id") == candidate.get("rule_id")
                same_location = accepted["path"] == candidate.get("path") and accepted["line"] == candidate.get("line")
                if same_location and (same_rule or accepted["title"].lower() == str(candidate.get("title", "")).lower()):
                    reporters.update(candidate.get("reported_by") or [])
            reporters.add("critic")
            accepted["reported_by"] = sorted(reporters - {"lead_synthesis"})
        report = normalize_report(final_raw, repository, number, "collaborative", gate.accepted)
        report["plan"] = plan
        report["critic_summary"] = str(critic.get("summary") or "")[:1500]
        report["gate_rejections"] = gate.rejected
        return report, self._metrics(calls, len(gate.rejected))

    @staticmethod
    def _registry(suite: RepositoryToolSuite) -> ToolRegistry:
        all_roles = frozenset({"lead", "security", "correctness_reliability", "critic"})
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                "list_changed_files",
                "List changed files and added-line counts.",
                suite.list_changed_files,
                all_roles,
            )
        )
        registry.register(
            AgentTool(
                "get_added_lines",
                "Read a bounded range of added lines from one changed file.",
                suite.get_added_lines,
                all_roles,
                required=frozenset({"path"}),
                optional=frozenset({"start_line", "end_line", "limit"}),
            )
        )
        registry.register(
            AgentTool(
                "search_added_code",
                "Search added code using a literal case-insensitive substring.",
                suite.search_added_code,
                all_roles,
                required=frozenset({"query"}),
                optional=frozenset({"path", "limit"}),
            )
        )
        registry.register(
            AgentTool(
                "get_diff_context",
                "Read added-line context around one exact added line.",
                suite.get_diff_context,
                frozenset({"security", "correctness_reliability", "critic"}),
                required=frozenset({"path", "line"}),
                optional=frozenset({"radius"}),
            )
        )
        return registry

    def _agentic(self, task_id: str, repository: str, number: int, diff: str) -> tuple[dict, dict]:
        parsed = parse_unified_diff(diff)
        suite = RepositoryToolSuite(parsed)
        registry = self._registry(suite)
        prior_runs = self.store.role_runs(task_id) if self.store else []
        ledger = RuntimeLedger(
            self.runtime_budget,
            calls=len(prior_runs),
            input_tokens=sum(run.get("input_tokens", 0) for run in prior_runs),
            output_tokens=sum(run.get("output_tokens", 0) for run in prior_runs),
            model_latency_ms=sum(run.get("latency_ms", 0) for run in prior_runs),
            tool_calls=len(self.store.tool_events(task_id)) if self.store else 0,
        )
        runtime = AgentRuntime(self.llm, registry, self.store, ledger)
        inventory = suite.list_changed_files()
        lead = runtime.run_role(
            task_id,
            "agentic:lead",
            "lead",
            1,
            AGENTIC_LEAD_MISSION,
            {"repository": repository, "pull_request": number, "inventory": inventory},
            {"list_changed_files", "get_added_lines", "search_added_code"},
        )

        def specialist(role: str, node: str, mission: str, focus_key: str) -> dict:
            return runtime.run_role(
                task_id,
                node,
                role,
                2,
                mission,
                {"lead_plan": lead, "assigned_focus": lead.get(focus_key, []), "inventory": inventory},
                {"list_changed_files", "get_added_lines", "search_added_code", "get_diff_context"},
            )

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="v3-agent") as pool:
            security_future = pool.submit(
                specialist, "security", "agentic:security", AGENTIC_SECURITY_MISSION, "security_focus"
            )
            correctness_future = pool.submit(
                specialist,
                "correctness_reliability",
                "agentic:correctness",
                AGENTIC_CORRECTNESS_MISSION,
                "correctness_focus",
            )
            security = security_future.result()
            correctness = correctness_future.result()

        candidates = []
        for role, raw in (("security", security), ("correctness_reliability", correctness)):
            for finding in raw.get("findings") or []:
                if isinstance(finding, dict):
                    value = dict(finding)
                    previous = value.get("reported_by")
                    if not isinstance(previous, list):
                        previous = [str(previous)] if previous else []
                    value["reported_by"] = sorted(set(previous + [role]))
                    candidates.append(value)

        critic = runtime.run_role(
            task_id,
            "agentic:critic",
            "critic",
            3,
            AGENTIC_CRITIC_MISSION,
            {"lead_plan": lead, "candidate_findings": candidates, "inventory": inventory},
            {"list_changed_files", "get_added_lines", "search_added_code", "get_diff_context"},
        )

        synthesis_node = "agentic:synthesis"
        checkpoint = self.store.get_checkpoint(task_id, synthesis_node) if self.store else None
        if checkpoint and checkpoint["state"] == "COMPLETED":
            final_raw = checkpoint["data"]["result"]
        else:
            ledger.before_call(lambda: bool(self.store and self.store.is_cancel_requested(task_id)))
            synthesis_context = {
                "lead_plan": lead,
                "critic_summary": critic.get("summary", ""),
                "approved_findings": critic.get("findings") or [],
            }
            final_raw, call = self._call(
                task_id, "lead_synthesis", 4, SYNTHESIS, json.dumps(synthesis_context, ensure_ascii=False)
            )
            ledger.record_model(call["input_tokens"], call["output_tokens"], call["latency_ms"])
            if self.store:
                self.store.save_checkpoint(task_id, synthesis_node, "COMPLETED", {"result": final_raw})

        # Preserve the reviewed records across the final model's prose-only synthesis.
        gate = validate_findings(critic.get("findings") or [], parsed, "critic")
        for accepted in gate.accepted:
            reporters = set(accepted.get("reported_by") or [])
            for candidate in candidates:
                same_rule = accepted.get("rule_id") and accepted.get("rule_id") == candidate.get("rule_id")
                same_location = accepted["path"] == candidate.get("path") and accepted["line"] == candidate.get("line")
                if same_location and (same_rule or accepted["title"].lower() == str(candidate.get("title", "")).lower()):
                    reporters.update(candidate.get("reported_by") or [])
            reporters.add("critic")
            accepted["reported_by"] = sorted(reporters - {"lead_synthesis"})
        report = normalize_report(final_raw, repository, number, "agentic", gate.accepted)
        report["plan"] = lead
        report["critic_summary"] = str(critic.get("summary") or "")[:1500]
        report["gate_rejections"] = gate.rejected
        metrics = ledger.snapshot()
        metrics["gate_rejected"] = len(gate.rejected)
        metrics["roles"] = ["lead", "security", "correctness_reliability", "critic", "lead_synthesis"]
        return report, metrics
