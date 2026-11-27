# 问题发布门禁：检查新增行定位、字段完整性、证据和置信度，同时保留拒绝原因以便追溯。

"""Deterministic finding and release gates shared by all run modes."""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .diff_parser import ParsedDiff
from .finding_identity import RULE_TO_CWE, is_valid_cwe
from .models import Finding, Severity


# 门禁输出：通过项、拒绝项及检查统计。
@dataclass
class GateResult:
    accepted: List[Finding]
    rejected: List[Dict[str, Any]]
    checks: Dict[str, Any]


# 决定候选是否满足发布条件，并解释被拒绝的原因。
class FindingGate:
    STRONG_EVIDENCE_TOOLS = {
        "ast_analyze", "symbol", "git_context", "run_scanners",
        "semgrep", "bandit", "eslint", "typecheck", "test", "diff-ast-analyze",
    }

    # 设置可发布问题的最低置信度，其余证据和字段规则由 apply 统一执行。
    def __init__(self, minimum_confidence: float = 0.55):
        self.minimum_confidence = minimum_confidence

    # 检查每条候选的格式、位置、证据与置信度，分别返回通过项和带原因的拒绝项。
    def apply(self, findings: Iterable[Finding], parsed: ParsedDiff) -> GateResult:
        valid_locations = {("new", item.path, item.line): item.content for item in parsed.added_lines}
        valid_locations.update({("old", item.path, item.line): item.content for item in parsed.removed_lines})
        accepted, rejected = [], []
        counters = {
            "format": 0, "taxonomy": 0, "evidence": 0,
            "confidence": 0, "release": 0,
        }
        for finding in findings:
            reasons = []
            location = (finding.line_side, finding.path, finding.line)
            if (
                location not in valid_locations or not finding.rule_id.strip()
                or not finding.title.strip() or not finding.explanation.strip()
            ):
                reasons.append("format gate: invalid location or required field")
                counters["format"] += 1

            expected_cwe = RULE_TO_CWE.get(str(finding.rule_id).strip().upper())
            if finding.cwe and not is_valid_cwe(finding.cwe):
                reasons.append("taxonomy gate: malformed CWE")
                counters["taxonomy"] += 1
            elif expected_cwe and str(finding.cwe or "").upper() != expected_cwe:
                reasons.append("taxonomy gate: CWE conflicts with program rule mapping")
                counters["taxonomy"] += 1

            quoted = finding.evidence.strip()
            line = valid_locations.get(location, "").strip()
            # 文本证据必须实际出现在定位到的新增行中，不能只依赖模型给出的引用。
            exact_line = bool(quoted and quoted in line)
            refs = [item for item in finding.evidence_refs if isinstance(item, dict)]
            valid_refs = [item for item in refs if item.get("evidence_id") and item.get("tool")]
            strong_refs = [
                item for item in valid_refs
                if str(item.get("tool")) in self.STRONG_EVIDENCE_TOOLS
            ]
            if not exact_line and not valid_refs and not finding.call_chain:
                reasons.append("evidence gate: no matching code, call chain or tool evidence")
                counters["evidence"] += 1
            # 高严重性问题还需要强工具证据或调用链，单行文本引用不足以放行。
            if finding.severity in {Severity.CRITICAL, Severity.HIGH} and not (
                strong_refs or finding.call_chain
            ):
                reasons.append(
                    "evidence gate: high-risk finding requires AST/scanner/call-chain evidence"
                )
                counters["evidence"] += 1
            if finding.confidence < self.minimum_confidence:
                reasons.append("confidence gate: score below %.2f" % self.minimum_confidence)
                counters["confidence"] += 1
            if finding.severity in {Severity.CRITICAL, Severity.HIGH} and (
                not finding.fix.strip() or not finding.test.strip()
            ):
                reasons.append("release gate: high-risk finding lacks fix or test guidance")
                counters["release"] += 1

            # 将门禁原因附在问题上，并另存拒绝摘要，便于解释为什么没有发布。
            finding.gate = {
                "passed": not reasons, "reasons": reasons,
                "exact_location_evidence": exact_line,
                "strong_evidence_count": len(strong_refs),
            }
            if reasons:
                rejected.append({
                    "rule_id": finding.rule_id, "path": finding.path,
                    "line": finding.line, "line_side": finding.line_side, "reasons": reasons,
                })
            else:
                accepted.append(finding)
        return GateResult(
            accepted, rejected,
            {
                "format": {"rejected": counters["format"]},
                "taxonomy": {"rejected": counters["taxonomy"]},
                "evidence": {"rejected": counters["evidence"]},
                "confidence": {
                    "minimum": self.minimum_confidence,
                    "rejected": counters["confidence"],
                },
                "release": {"rejected": counters["release"]},
                "accepted": len(accepted), "rejected": len(rejected),
            },
        )
