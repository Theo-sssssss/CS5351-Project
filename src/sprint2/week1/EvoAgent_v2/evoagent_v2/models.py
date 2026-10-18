from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SEVERITIES = {"critical", "high", "medium", "low"}
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
MODES = {"baseline", "collaborative"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def normalize_finding(raw: dict, reported_by: str = "model") -> dict:
    severity = _text(raw.get("severity", "medium"), 20).lower()
    if severity not in SEVERITIES:
        severity = "medium"
    try:
        line = max(0, int(raw.get("line", 0)))
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
        "rule_id": _text(raw.get("rule_id"), 180),
        "category": _text(raw.get("category"), 80).lower() or "general",
        "severity": severity,
        "title": _text(raw.get("title"), 180) or "Code review finding",
        "explanation": _text(raw.get("explanation"), 3000),
        "path": _text(raw.get("path"), 500),
        "line": line,
        "evidence": _text(raw.get("evidence"), 1500),
        "fix": _text(raw.get("fix"), 3000),
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
        "summary": _text(raw.get("summary"), 1500) or ("未发现可发布问题。" if not ordered else "审查发现可操作问题。"),
        "risk": report_risk(ordered),
        "findings": ordered,
        "created_at": now(),
    }
