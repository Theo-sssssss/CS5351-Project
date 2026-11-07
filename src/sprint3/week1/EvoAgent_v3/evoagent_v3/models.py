from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


SEVERITIES = {"critical", "high", "medium", "low"}
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
MODES = {"baseline", "collaborative", "agentic"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def normalize_finding(raw: dict, reported_by: str = "model") -> dict:
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    evidence_value = raw.get("evidence")
    evidence_obj = evidence_value if isinstance(evidence_value, dict) else {}
    line_value = raw.get("line") or location.get("line") or evidence_obj.get("line")
    if not line_value:
        lines = location.get("lines") or evidence_obj.get("lines")
        if isinstance(lines, list) and len(lines) == 1:
            line_value = lines[0]
    path_value = raw.get("path") or raw.get("file") or location.get("file") or location.get("path") or evidence_obj.get("file")
    evidence_text = raw.get("code") or evidence_obj.get("code") or evidence_obj.get("text") or evidence_value
    if not path_value and isinstance(evidence_value, str):
        inline = re.fullmatch(r"Line\s+(\d+)\s+in\s+([\w./-]+):\s*(.+)", evidence_value.strip(), re.IGNORECASE)
        if inline:
            line_value = line_value or inline.group(1)
            path_value = inline.group(2)
            evidence_text = inline.group(3)
    severity = _text(raw.get("severity", "medium"), 20).lower()
    if severity not in SEVERITIES:
        severity = "medium"
    try:
        line = max(0, int(line_value or 0))
    except (TypeError, ValueError):
        line = 0
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.7))))
    except (TypeError, ValueError):
        confidence = 0.7
    reporters = raw.get("reported_by")
    if not isinstance(reporters, list):
        reporters = [reported_by]
    reporters = sorted({_text(item, 80) for item in reporters if _text(item, 80)})
    return {
        "rule_id": _text(raw.get("rule_id") or raw.get("id"), 180),
        "category": _text(raw.get("category"), 80).lower() or "general",
        "severity": severity,
        "title": _text(raw.get("title") or raw.get("type"), 180) or "Code review finding",
        "explanation": _text(raw.get("explanation") or raw.get("description"), 3000),
        "path": _text(path_value, 500),
        "line": line,
        "evidence": _text(evidence_text, 1500),
        "fix": _text(raw.get("fix") or raw.get("recommendation"), 3000),
        "test": _text(raw.get("test"), 2000),
        "confidence": confidence,
        "reported_by": reporters,
    }


def report_risk(findings: list[dict]) -> str:
    if not findings:
        return "low"
    return sorted(findings, key=lambda item: SEVERITY_RANK[item["severity"]])[0]["severity"]


def normalize_report(raw: dict, repository: str, number: int, mode: str, findings: list[dict]) -> dict:
    ordered = sorted(findings, key=lambda item: (SEVERITY_RANK[item["severity"]], item["path"], item["line"], item["title"]))
    return {
        "repository": repository,
        "pull_request": number,
        "mode": mode,
        "summary": (_text(raw.get("summary"), 1500) or "The review found actionable issues.") if ordered else "No publishable findings passed evidence and integrity validation; this does not mean the code is defect-free.",
        "model_summary": _text(raw.get("summary"), 1500),
        "risk": report_risk(ordered),
        "findings": ordered,
        "created_at": now(),
    }
