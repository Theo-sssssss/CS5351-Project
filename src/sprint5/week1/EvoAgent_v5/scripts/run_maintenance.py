"""Run the fixed, safe V5 maintenance checks.

The script is intentionally limited to repository-owned checks. It does not
accept arbitrary commands and it never changes source files.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ("unit tests", (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"), True),
    ("Python compilation", (sys.executable, "-m", "compileall", "-q", "evoagent"), True),
    ("JavaScript syntax", ("node", "--check", "web/app.js"), False),
)


def diagnose(output: str) -> str:
    value = output.lower()
    if "syntaxerror" in value:
        return "Syntax error: fix the first reported file and line."
    if "assertionerror" in value or "failed" in value:
        return "Test regression: reproduce the first failure and add a focused regression test."
    if "modulenotfounderror" in value or "importerror" in value:
        return "Dependency or import failure: install requirements and verify the import path."
    return "Review the first error in the captured output, then rerun this fixed check."


def main() -> int:
    failed = False
    for name, command, required in CHECKS:
        if shutil.which(command[0]) is None:
            status = "FAILED" if required else "SKIPPED"
            print(f"{status}: {name} (required tool is unavailable)")
            failed = failed or required
            continue
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if result.returncode == 0:
            print(f"PASSED: {name}")
            continue
        failed = True
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        print(f"FAILED: {name} — {diagnose(output)}")
        if output:
            print(output[-4000:])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
