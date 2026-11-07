from __future__ import annotations

import re
from dataclasses import dataclass, field


HUNK = re.compile(r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")


def normalize_path(path: str) -> str:
    value = str(path or "").strip().strip('"')
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return value


@dataclass(frozen=True)
class AddedLine:
    path: str
    line: int
    text: str


@dataclass
class ParsedDiff:
    raw: str
    files: set[str] = field(default_factory=set)
    added_lines: list[AddedLine] = field(default_factory=list)

    def lines_for(self, path: str) -> dict[int, str]:
        target = normalize_path(path)
        return {item.line: item.text for item in self.added_lines if item.path == target}

    def locate_evidence(self, path: str, evidence: str) -> list[int]:
        needle = " ".join(str(evidence or "").strip().split())
        if not needle:
            return []
        matches = []
        for line, text in self.lines_for(path).items():
            haystack = " ".join(text.strip().split())
            if needle in haystack or haystack in needle:
                matches.append(line)
        return matches


def parse_unified_diff(raw: str) -> ParsedDiff:
    parsed = ParsedDiff(raw=raw)
    current_path = ""
    old_line = new_line = 0
    in_hunk = False
    for raw_line in raw.splitlines():
        if raw_line.startswith("+++ "):
            candidate = raw_line[4:].split("\t", 1)[0]
            current_path = "" if candidate == "/dev/null" else normalize_path(candidate)
            if current_path:
                parsed.files.add(current_path)
            in_hunk = False
            continue
        match = HUNK.match(raw_line)
        if match:
            old_line, new_line = int(match.group("old")), int(match.group("new"))
            in_hunk = True
            continue
        if not in_hunk or not current_path:
            continue
        if raw_line.startswith("+"):
            parsed.added_lines.append(AddedLine(current_path, new_line, raw_line[1:]))
            new_line += 1
        elif raw_line.startswith("-"):
            old_line += 1
        elif raw_line.startswith("\\ No newline"):
            continue
        else:
            old_line += 1
            new_line += 1
    return parsed
