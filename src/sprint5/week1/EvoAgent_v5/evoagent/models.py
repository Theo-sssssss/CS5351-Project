# 共享数据模型：定义任务状态、严重性、变更行、问题、报告和轨迹事件，统一序列化格式。

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# 任务生命周期状态，用于状态机转换和对外进度展示。
class TaskState(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    PAUSED_BUDGET = "PAUSED_BUDGET"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# 问题严重性枚举，保证排序、门禁和报告使用相同取值。
class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# 执行组件类别，用于区分模型 Agent、工具扫描器与门禁。
class ComponentKind(str, Enum):
    """Product-level component taxonomy; names describe behavior, not branding."""

    LLM_AGENT = "llm-agent"
    TOOL_SCANNER = "tool-scanner"
    GATE = "gate"


# 新增代码行的位置与内容，行号对应新文件。
@dataclass
class ChangedLine:
    path: str
    line: int
    content: str


# 结构化审查问题，包含定位、证据、修复建议和置信度。
@dataclass
class Finding:
    rule_id: str
    severity: Severity
    title: str
    explanation: str
    path: str
    line: int
    evidence: str
    fix: str
    test: str
    confidence: float = 0.8
    evidence_refs: List[Dict[str, Any]] = field(default_factory=list)
    call_chain: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "unknown"
    # Preserve every corroborating producer when scanner and model findings merge.
    sources: List[str] = field(default_factory=list)
    gate: Dict[str, Any] = field(default_factory=dict)
    # Canonical taxonomy used for evaluation.  rule_id remains an internal or
    # reviewer-specific label and is not required to be stable across models.
    cwe: Optional[str] = None
    line_side: str = "new"

    # 将内部对象转换为可 JSON 序列化的字典，枚举使用其对外字符串值。
    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["severity"] = self.severity.value
        return value


# 完整审查报告，聚合问题、风险、协作及执行统计。
@dataclass
class ReviewReport:
    repository: str
    pull_request: Optional[int]
    summary: str
    risk: str
    findings: List[Finding] = field(default_factory=list)
    files_reviewed: List[str] = field(default_factory=list)
    reviewer: str = "local-rules"
    collaboration: Dict[str, Any] = field(default_factory=dict)
    run_mode: Dict[str, Any] = field(default_factory=dict)
    components: List[Dict[str, Any]] = field(default_factory=list)
    execution: Dict[str, Any] = field(default_factory=dict)

    # 将内部对象转换为可 JSON 序列化的字典，枚举使用其对外字符串值。
    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository": self.repository,
            "pull_request": self.pull_request,
            "summary": self.summary,
            "risk": self.risk,
            "findings": [item.to_dict() for item in self.findings],
            "files_reviewed": self.files_reviewed,
            "reviewer": self.reviewer,
            "collaboration": self.collaboration,
            "run_mode": self.run_mode,
            "components": self.components,
            "execution": self.execution,
        }


# 任务状态变化记录，使用递增步数和时间标识执行顺序。
@dataclass
class TraceEvent:
    step: int
    state: TaskState
    message: str
    created_at: str

    # 将内部对象转换为可 JSON 序列化的字典，枚举使用其对外字符串值。
    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value
