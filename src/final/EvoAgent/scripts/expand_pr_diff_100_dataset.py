"""Expand the 100 synthetic PR fixtures into contextual, reproducible diffs.

Run from the repository root with ``python scripts/expand_pr_diff_100_dataset.py``.
The generated modules are parsed as code but never imported or executed.
"""

import ast
import difflib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from evoagent.patching import FilePatch, Hunk, apply_file_patch, parse_unified_patch


DATASET = ROOT / "evaluation_data" / "pr_diff_100.jsonl"
CORE_START = "# fixture-core:start"
CORE_END = "# fixture-core:end"


def original_before(case):
    """Reverse the checked-in patch to recover its original file contents."""
    path, after = next(iter(case["after_files"].items()))
    patch = parse_unified_patch(case["diff"], [path])[0]
    reverse = FilePatch(path, [
        Hunk(
            old_start=hunk.new_start,
            old_count=hunk.new_count,
            new_start=hunk.old_start,
            new_count=hunk.old_count,
            lines=[
                ("-" + line[1:] if line.startswith("+") else
                 "+" + line[1:] if line.startswith("-") else line)
                for line in hunk.lines
            ],
        )
        for hunk in patch.hunks
    ])
    return path, apply_file_patch(after, reverse), after


def extract_core(content):
    """Recover an earlier expanded fixture's compact process function."""
    start = content.index(CORE_START) + len(CORE_START)
    end = content.index(CORE_END)
    return content[start:end].strip("\n") + "\n"


def module_text(core, repository_number, after):
    imports = """from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import pickle
import random
import subprocess
import tempfile
import time
from typing import Any, Mapping

"""
    shared = '''SERVICE_NAME = "fixture-service-{repo:02d}"
DEFAULT_TIMEOUT_SECONDS = 5


def normalize_request(value: Any) -> str:
    """Normalize one synthetic request without retaining its original value."""
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("request value is required")
    return normalized


'''.format(repo=repository_number)
    if after:
        revision = '''SCHEMA_VERSION = 2
MAX_INPUT_SIZE = 8192


def build_request_context(value: Any, attributes: Mapping[str, Any] | None = None) -> dict:
    """Build bounded metadata used by the synthetic service pipeline."""
    normalized = normalize_request(value)
    if len(normalized) > MAX_INPUT_SIZE:
        raise ValueError("request value is too large")
    supplied = dict(attributes or {})
    return {
        "service": SERVICE_NAME,
        "schema_version": SCHEMA_VERSION,
        "value_length": len(normalized),
        "attribute_count": len(supplied),
    }


'''
        footer = '''

def summarize_result(value: Any) -> dict:
    """Return stable metadata for an offline fixture result."""
    context = build_request_context(value)
    context["status"] = "processed"
    context["timeout_seconds"] = DEFAULT_TIMEOUT_SECONDS
    return context
'''
    else:
        revision = '''SCHEMA_VERSION = 1


def build_request_context(value: Any) -> dict:
    """Build the original minimal request metadata."""
    normalized = normalize_request(value)
    return {
        "service": SERVICE_NAME,
        "schema_version": SCHEMA_VERSION,
        "value_length": len(normalized),
    }


'''
        footer = '''

def summarize_result(value: Any) -> dict:
    """Return metadata for an offline fixture result."""
    context = build_request_context(value)
    context["status"] = "processed"
    return context
'''
    return (
        '"""Synthetic PR fixture; all names and values are fictional."""\n\n'
        + imports + shared + revision + CORE_START + "\n" + core + CORE_END + footer
    )


def expand(cases):
    for index, case in enumerate(cases):
        source = case.get("source") or {}
        if source.get("generator") == "evoagent-e2e-v2-contextual":
            path = next(iter(case["after_files"]))
            before_core = extract_core(case["before_files"][path])
            after_core = extract_core(case["after_files"][path])
            label_source_lines = case["after_files"][path].splitlines()
        else:
            path, before_core, after_core = original_before(case)
            label_source_lines = after_core.splitlines()

        repository_number = int(case["repository"].rsplit("-", 1)[1])
        needles = []
        for finding in case["expected_findings"]:
            needles.append(label_source_lines[int(finding["start_line"]) - 1].strip())

        before = module_text(before_core, repository_number, False)
        after = module_text(after_core, repository_number, True)
        ast.parse(before, filename=path)
        ast.parse(after, filename=path)
        diff = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="a/" + path, tofile="b/" + path, n=10,
        ))
        added = {
            item.line: item.content.strip()
            for item in __import__("evoagent.diff_parser", fromlist=["parse_unified_diff"])
            .parse_unified_diff(diff).added_lines
        }
        for finding, needle in zip(case["expected_findings"], needles):
            matches = [line for line, text in added.items() if text == needle]
            if len(matches) != 1:
                raise ValueError("could not relocate finding in %s: %r" % (case["id"], needle))
            finding["start_line"] = finding["end_line"] = matches[0]

        case["before_files"] = {path: before}
        case["after_files"] = {path: after}
        case["diff"] = diff
        case["source"] = {
            "generator": "evoagent-e2e-v2-contextual",
            "kind": "offline-fixture",
            "public_url": None,
        }
    return cases


def main():
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]
    if len(cases) != 100:
        raise ValueError("expected exactly 100 fixtures")
    content = "".join(
        json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n"
        for case in expand(cases)
    )
    with DATASET.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    lengths = [len(case["diff"].splitlines()) for case in cases]
    print("Expanded %d fixtures; diff lines: %d-%d" % (len(cases), min(lengths), max(lengths)))


if __name__ == "__main__":
    main()
