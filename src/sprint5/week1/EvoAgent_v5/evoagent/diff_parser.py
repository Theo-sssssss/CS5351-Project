# 统一 Diff 解析：记录变更文件以及新增行在新文件中的行号，供审查定位和门禁使用。

import re
from dataclasses import dataclass, field
from typing import List

from .models import ChangedLine


# 审查所需的精简 Diff 结果：变更文件列表与新增行列表。
@dataclass
class ParsedDiff:
    files: List[str]
    added_lines: List[ChangedLine]
    removed_lines: List[ChangedLine] = field(default_factory=list)


HUNK = re.compile(r"^@@ -(?:\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


# 沿 Diff 块维护新文件行号，只收集新增行及其文件路径。
def parse_unified_diff(diff: str) -> ParsedDiff:
    files: List[str] = []
    added: List[ChangedLine] = []
    current_path = ""
    new_line = 0
    in_hunk = False

    for raw in diff.splitlines():
        # 文件头决定后续新增行属于哪个新文件；删除文件的目标路径是 /dev/null。
        if raw.startswith("+++ "):
            current_path = raw[4:].strip()
            if current_path.startswith("b/"):
                current_path = current_path[2:]
            if current_path != "/dev/null" and current_path not in files:
                files.append(current_path)
            in_hunk = False
            continue
        match = HUNK.match(raw)
        # 每个 hunk 都重新给出新文件起始行号，不能沿用上一个块的计数。
        if match:
            new_line = int(match.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append(ChangedLine(current_path or "unknown", new_line, raw[1:]))
            new_line += 1
        # 删除行只占旧文件行号，新文件行号保持不变。
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        # 这是 Diff 格式提示，不对应实际代码行。
        elif raw.startswith("\\ No newline"):
            continue
        else:
            new_line += 1

    return ParsedDiff(files=files, added_lines=added)

