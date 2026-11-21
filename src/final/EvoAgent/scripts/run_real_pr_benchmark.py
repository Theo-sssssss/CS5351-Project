# 真实 PR 基准入口：复用多 Agent 评测脚本的参数与执行流程。

"""Validate a real PR dataset before wiring model-backed reviewer factories."""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evoagent.evaluation_harness import load_jsonl  # noqa: E402
from evoagent.evaluation_v2 import validate_real_dataset  # noqa: E402


# 解析命令行参数，准备本脚本所需输入，执行实验或导入并写出结果。
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="Labelled public/historical PR JSONL")
    parser.add_argument("--minimum", type=int, default=300)
    args = parser.parse_args()
    result = validate_real_dataset(load_jsonl(args.dataset), args.minimum)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
