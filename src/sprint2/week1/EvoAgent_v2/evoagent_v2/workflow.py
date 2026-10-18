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
from .prompts import BASELINE, CORRECTNESS, CRITIC, LEAD_PLAN, SECURITY, SYNTHESIS


class LLMProtocol(Protocol):
    model: str

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMResult: ...


class WorkflowEngine:
    def __init__(self, llm: LLMProtocol, store=None):
        self.llm = llm
        self.store = store

    def review(self, task_id: str, repository: str, number: int, diff: str, mode: str) -> tuple[dict, dict]:
        if mode == "baseline":
            return self._baseline(task_id, repository, number, diff)
        if mode == "collaborative":
            return self._collaborative(task_id, repository, number, diff)
        raise ValueError("mode must be baseline or collaborative")

    def _call(self, task_id: str, role: str, phase: int, prompt: str, user: str) -> tuple[dict, dict]:
        digest = hashlib.sha256(user.encode("utf-8")).hexdigest()
        run_id = self.store.start_role(task_id, role, phase, self.llm.model, digest) if self.store else 0
        started = time.monotonic()
        try:
            result = self.llm.complete_json(prompt, user)
            latency_ms = max(0, round((time.monotonic() - started) * 1000))
            if self.store:
                self.store.finish_role(run_id, result.value, latency_ms, result.input_tokens, result.output_tokens)
            return result.value, {
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

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="v2-specialist") as pool:
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
        gate = validate_findings(final_raw.get("findings") or [], parsed, "lead_synthesis")
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
