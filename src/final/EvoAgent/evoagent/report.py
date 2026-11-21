# 报告渲染：把结构化审查结果转换为 Markdown，供报告接口和 GitHub 评论复用。

from typing import Any, Dict


# 按报告结构渲染摘要、问题、证据、修复与执行信息，供下载和评论复用。
def to_markdown(report: Dict[str, Any]) -> str:
    title = "# EvoAgent PR Review"
    if report.get("pull_request") is not None:
        title += " — #%s" % report["pull_request"]
    lines = [
        title,
        "",
        "**Repository:** `%s`  " % report.get("repository", ""),
        "**Risk:** `%s`  " % report.get("risk", "unknown"),
        "**Reviewer:** `%s`" % report.get("reviewer", "unknown"),
        "",
        report.get("summary", ""),
        "",
    ]
    run_mode = report.get("run_mode") or {}
    execution = report.get("execution") or {}
    coverage = execution.get("coverage")
    if coverage is not None:
        lines.extend(["## Diff coverage", "",
                      "- Text batches: %s/%s complete" % (coverage["completed"], coverage["total"])])
        for batch in coverage.get("batches", []):
            if batch["status"] != "completed":
                lines.append("- Unreviewed batch %s: %s" % (batch["id"], ", ".join(batch["files"])))
        for item in coverage.get("metadata", []):
            lines.append("- File metadata: %s (%s)" % (item["path"], item["kind"]))
        lines.append("")
    if run_mode:
        lines.extend([
            "## Execution facts",
            "",
            "- Mode: requested `%s`, effective `%s`" % (
                run_mode.get("requested", "unknown"), run_mode.get("effective", "unknown")
            ),
            "- Model calls: `%s`; tool calls: `%s`" % (
                execution.get("llm_calls", 0), execution.get("tool_calls", 0)
            ),
            "- Tokens: input `%s`, output `%s`, total `%s`" % (
                execution.get("input_tokens", 0), execution.get("output_tokens", 0),
                execution.get("total_tokens", 0),
            ),
            "- Token cost: `$%.8f`; latency: `%s ms`" % (
                float(execution.get("cost_usd", 0) or 0), execution.get("duration_ms", 0)
            ),
            "",
        ])
        if run_mode.get("fallback_reason"):
            lines.extend(["> %s" % run_mode["fallback_reason"], ""])
        context = execution.get("context_management") or {}
        if context:
            memory = context.get("memory_recall") or {}
            lines[-1:-1] = [
                "- Context compression: `%s` view(s), estimated reduction `%.1f%%`; "
                "recalled memories `%s`" % (
                    context.get("compression_calls", 0),
                    max(0.0, float(context.get("estimated_reduction_ratio", 0) or 0) * 100),
                    memory.get("recalled", 0),
                )
            ]
    collaboration = report.get("collaboration") or {}
    if collaboration and run_mode.get("effective") == "agentic" and execution.get("llm_calls", 0):
        lines.extend([
            "## LLM Agent collaboration",
            "",
            "- Protocol: `%s`" % collaboration.get("protocol", "unknown"),
            "- Actual roles: `%s`" % ", ".join(collaboration.get("roles") or []),
            "- Candidate findings: `%s`; critic decisions: `%s`" % (
                collaboration.get("candidate_findings", 0),
                len(collaboration.get("critic_decisions") or []),
            ),
            "",
        ])
    findings = report.get("findings", [])
    if not findings:
        lines.append("No actionable issue in the reviewed text." if coverage is not None else
                     "✅ No actionable issue detected in the added lines.")
        return "\n".join(lines) + "\n"
    lines.extend(["## Findings", ""])
    icons = {"critical": "🚨", "high": "🔴", "medium": "🟠", "low": "🟡"}
    for index, item in enumerate(findings, 1):
        severity = item.get("severity", "medium")
        lines.extend(
            [
                "### %d. %s %s" % (index, icons.get(severity, "•"), item.get("title", "Finding")),
                "",
                "`%s:%s` · **%s** · `%s`" % (
                    item.get("path", ""), ("old " if item.get("line_side") == "old" else "") + str(item.get("line", 0)),
                    severity.upper(), item.get("rule_id", "")),
                "",
                item.get("explanation", ""),
                "",
                "**Evidence**",
                "",
                "```text",
                item.get("evidence", ""),
                "```",
                "",
                "**Evidence references:** %s" % (
                    ", ".join(
                        "`%s`" % ref.get("evidence_id", "")
                        for ref in item.get("evidence_refs", []) if ref.get("evidence_id")
                    ) or "none"
                ),
                "",
                "**Suggested fix:** %s" % item.get("fix", ""),
                "",
                "**Suggested test:** %s" % item.get("test", ""),
                "",
            ]
        )
    return "\n".join(lines) + "\n"
