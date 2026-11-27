# 可观测性接入：按配置创建 OpenTelemetry Span，并依据任务失败率生成持久化告警。

"""Tracing helpers that degrade cleanly when OpenTelemetry is not installed."""
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional


trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
logger = logging.getLogger("evoagent")


# 可选的追踪接入层，业务代码通过上下文管理器记录 Span。
class Observability:
    # 根据配置初始化可选追踪组件，未配置导出端点时保留本地调用接口。
    def __init__(self, service_name: str = "evoagent", endpoint: str = ""):
        self.tracer = None
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
            if endpoint:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            trace.set_tracer_provider(provider)
            self.tracer = trace.get_tracer(service_name)
        except ImportError:
            self.tracer = None

    # 包装一次操作的观测上下文，配置不可用时仍允许业务继续执行。
    @contextmanager
    def span(self, name: str, trace_id: str = "", **attributes):
        token = trace_id_var.set(trace_id or trace_id_var.get())
        if self.tracer:
            with self.tracer.start_as_current_span(name) as span:
                for key, value in attributes.items():
                    if value is not None:
                        span.set_attribute(key, value)
                try:
                    yield span
                except Exception as exc:
                    span.record_exception(exc)
                    raise
                finally:
                    trace_id_var.reset(token)
        else:
            try:
                yield None
            finally:
                trace_id_var.reset(token)


# 根据租户任务统计判定是否需要写入失败率告警。
class AlertManager:
    # 保存告警存储、失败率阈值和最少样本数，供任务结束后评估。
    def __init__(self, store, failure_rate: float = .2, min_samples: int = 10):
        self.store = store
        self.failure_rate = failure_rate
        self.min_samples = min_samples

    # 读取租户任务统计，达到最小样本量且失败率超阈值时创建告警。
    def evaluate(self, tenant_id: str) -> None:
        stats = self.store.dashboard_stats(tenant_id)
        if stats["tasks_total"] >= self.min_samples:
            rate = stats["tasks_failed"] / stats["tasks_total"]
            if rate > self.failure_rate:
                self.store.create_alert(
                    tenant_id, "review-failure-rate", "critical",
                    "Review failure rate %.1f%% exceeds the %.1f%% threshold."
                    % (rate * 100, self.failure_rate * 100),
                )
