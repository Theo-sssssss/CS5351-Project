# 运行模式与组件分类：解析 agentic 模式，并向报告暴露 Agent、工具和门禁的职责分类。

"""Agentic execution mode and product component taxonomy."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, Optional

from .models import ComponentKind


# 当前支持的审查运行模式。
class RunMode(str, Enum):
    AGENTIC = "agentic"

    # 解析并验证运行模式，拒绝不支持的模式值。
    @classmethod
    def parse(cls, value: Optional[str], default: "RunMode" = None) -> "RunMode":
        fallback = default or cls.AGENTIC
        if value is None or not str(value).strip():
            return fallback
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            raise ValueError("mode must be agentic") from exc


# 记录请求模式、实际模式及解析说明。
@dataclass(frozen=True)
class ModeResolution:
    requested: RunMode
    effective: RunMode
    model_configured: bool
    fallback_reason: str = ""

    # 将内部对象转换为可 JSON 序列化的字典，枚举使用其对外字符串值。
    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested": self.requested.value,
            "effective": self.effective.value,
            "model_configured": self.model_configured,
            "fallback_reason": self.fallback_reason,
        }


# 生成运行模式解析结果，说明请求模式和实际采用模式。
def resolve_mode(requested: Optional[str], model_configured: bool) -> ModeResolution:
    selected = RunMode.parse(requested, RunMode.AGENTIC)
    unavailable = "" if model_configured else "Agentic review requires a configured model."
    return ModeResolution(selected, selected, model_configured, unavailable)


# 构造组件分类记录，让报告区分 Agent、工具扫描器和门禁。
def component(kind: ComponentKind, name: str, enabled: bool = True, **detail) -> dict:
    return {"kind": kind.value, "name": name, "enabled": bool(enabled), **detail}


# 返回对外组件分类说明，供 API 和控制台展示。
def public_taxonomy() -> Dict[str, Any]:
    return {
        "component_kinds": {
            ComponentKind.LLM_AGENT.value: (
                "Reasons from a goal, autonomously selects tools or stops, and may revise."
            ),
            ComponentKind.TOOL_SCANNER.value: (
                "Produces facts through rules, AST, Semgrep, code search or command execution."
            ),
            ComponentKind.GATE.value: (
                "Validates format, evidence, confidence and release eligibility."
            ),
        },
        "run_modes": {
            RunMode.AGENTIC.value: (
                "A Lead delegates to Security and Correctness/Reliability workers, a blind "
                "Critic verifies once, and the Lead performs final synthesis."
            ),
        },
    }
