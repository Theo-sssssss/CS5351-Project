# 进程内指标：线程安全地累计请求计数和耗时，并输出 Prometheus 文本格式。

import threading
import time
from collections import defaultdict
from contextlib import contextmanager


# 进程内共享指标容器，用锁保护并发计数与耗时更新。
class Metrics:
    # 创建计数和耗时容器，并用锁保护多个请求线程的更新。
    def __init__(self):
        self._lock = threading.Lock()
        self.counters = defaultdict(float)
        self.duration_sum = defaultdict(float)
        self.duration_count = defaultdict(int)

    # 在锁内累加指定指标，避免并发请求丢失计数。
    def inc(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self.counters[name] += value

    # 测量上下文内操作的耗时，并在退出时更新统计。
    @contextmanager
    def timer(self, name: str):
        started = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - started
            with self._lock:
                self.duration_sum[name] += elapsed
                self.duration_count[name] += 1

    # 将当前指标快照渲染为 Prometheus 可抓取的文本。
    def prometheus(self) -> str:
        with self._lock:
            lines = []
            for name, value in sorted(self.counters.items()):
                lines.extend(["# TYPE evoagent_%s counter" % name, "evoagent_%s %s" % (name, value)])
            for name, value in sorted(self.duration_sum.items()):
                lines.extend([
                    "# TYPE evoagent_%s_seconds summary" % name,
                    "evoagent_%s_seconds_sum %s" % (name, value),
                    "evoagent_%s_seconds_count %s" % (name, self.duration_count[name]),
                ])
        return "\n".join(lines) + "\n"


metrics = Metrics()

