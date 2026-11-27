# 命令行入口：执行 python -m evoagent 时启动 HTTP 服务。

from .api import run


if __name__ == "__main__":
    run()

