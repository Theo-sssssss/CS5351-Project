from __future__ import annotations

from .diff_parser import ParsedDiff, normalize_path


class RepositoryToolSuite:
    """Read-only tools over the pull-request diff supplied to one review task."""

    def __init__(self, parsed: ParsedDiff):
        self.parsed = parsed

    def list_changed_files(self) -> dict:
        files = []
        for path in sorted(self.parsed.files):
            files.append({"path": path, "added_lines": len(self.parsed.lines_for(path))})
        return {"files": files, "count": len(files)}

    def get_added_lines(self, path: str, start_line: int = 0, end_line: int = 0, limit: int = 80) -> dict:
        target = normalize_path(path)
        if target not in self.parsed.files:
            raise ValueError("path is not present in the diff")
        safe_limit = max(1, min(int(limit), 120))
        start = max(0, int(start_line or 0))
        end = max(0, int(end_line or 0))
        values = []
        for line, text in sorted(self.parsed.lines_for(target).items()):
            if start and line < start:
                continue
            if end and line > end:
                continue
            values.append({"line": line, "text": text})
            if len(values) > safe_limit:
                break
        return {"path": target, "lines": values[:safe_limit], "truncated": len(values) > safe_limit}

    def search_added_code(self, query: str, path: str = "", limit: int = 30) -> dict:
        needle = str(query or "").strip().lower()
        if not needle:
            raise ValueError("query is required")
        target = normalize_path(path)
        if target and target not in self.parsed.files:
            raise ValueError("path is not present in the diff")
        safe_limit = max(1, min(int(limit), 60))
        matches = []
        for item in self.parsed.added_lines:
            if target and item.path != target:
                continue
            if needle in item.text.lower():
                matches.append({"path": item.path, "line": item.line, "text": item.text})
                if len(matches) > safe_limit:
                    break
        return {"query": query, "matches": matches[:safe_limit], "truncated": len(matches) > safe_limit}

    def get_diff_context(self, path: str, line: int, radius: int = 3) -> dict:
        target = normalize_path(path)
        if target not in self.parsed.files:
            raise ValueError("path is not present in the diff")
        center = int(line)
        safe_radius = max(0, min(int(radius), 10))
        line_map = self.parsed.lines_for(target)
        values = [
            {"line": number, "text": text, "target": number == center}
            for number, text in sorted(line_map.items())
            if center - safe_radius <= number <= center + safe_radius
        ]
        if center not in line_map:
            raise ValueError("line is not an added line in the diff")
        return {"path": target, "center_line": center, "lines": values}
