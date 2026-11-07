from __future__ import annotations

from dataclasses import dataclass

from .diff_parser import ParsedDiff, normalize_path
from .models import normalize_finding


@dataclass
class GateResult:
    accepted: list[dict]
    rejected: list[dict]


def _reject(item: dict, reason: str) -> dict:
    return {"finding": item, "reason": reason}


def validate_findings(raw_findings: list[dict], parsed: ParsedDiff, reported_by: str = "model") -> GateResult:
    accepted: list[dict] = []
    rejected: list[dict] = []
    seen: dict[tuple, dict] = {}
    for raw in raw_findings:
        if not isinstance(raw, dict):
            rejected.append(_reject({}, "finding_not_object"))
            continue
        item = normalize_finding(raw, reported_by)
        item["path"] = normalize_path(item["path"])
        if item["path"] not in parsed.files:
            rejected.append(_reject(item, "path_not_in_diff"))
            continue
        line_map = parsed.lines_for(item["path"])
        if item["line"] not in line_map:
            candidates = parsed.locate_evidence(item["path"], item["evidence"])
            if len(candidates) == 1:
                item["line"] = candidates[0]
            else:
                rejected.append(_reject(item, "line_not_added"))
                continue
        evidence = " ".join(item["evidence"].split())
        changed = " ".join(line_map[item["line"]].strip().split())
        if not evidence or evidence != changed:
            rejected.append(_reject(item, "evidence_not_on_added_line"))
            continue
        if not item["explanation"]:
            rejected.append(_reject(item, "missing_explanation"))
            continue
        identity = (item["rule_id"] or item["title"].lower(), item["path"], item["line"])
        if identity in seen:
            existing = seen[identity]
            existing["reported_by"] = sorted(set(existing["reported_by"] + item["reported_by"]))
            existing["confidence"] = max(existing["confidence"], item["confidence"])
            rejected.append(_reject(item, "duplicate"))
            continue
        seen[identity] = item
        accepted.append(item)
    return GateResult(accepted=accepted, rejected=rejected)
