# 异步任务投递：支持内存线程池和 Redis Streams；处理重试、租约回收及死信记录。
# Redis 消息完成、重新入队或写入死信后才确认 ACK；基础设施异常时保留待处理消息。

"""Durable task delivery with ACK, leases, retry backoff and a dead-letter queue."""
import json
import queue
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional


# 标记无法通过重试恢复的投递错误，直接进入死信流程。
class PermanentTaskError(RuntimeError):
    """An error that must not be retried."""


class QueueLeaseBusy(RuntimeError):
    """Leave a claimed Redis delivery pending while its durable owner is running."""


# 异步投递队列，按配置使用线程池或 Redis 消费组。
class TaskQueue:
    STREAM = "evoagent:review:stream"
    DLQ = "evoagent:review:dlq"
    GROUP = "evoagent-workers"

    # 配置投递策略与线程池；设置 Redis 地址时连接消费组并启动队列 Worker。
    def __init__(
        self, handler: Callable[[Dict[str, Any]], None], workers: int = 2,
        redis_url: str = "", max_attempts: int = 3, lease_seconds: int = 60,
        on_dead_letter: Optional[Callable[[Dict[str, Any], str], None]] = None,
    ):
        self.handler = handler
        self.redis_url = redis_url
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        self.on_dead_letter = on_dead_letter
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="evoagent-worker")
        self._redis = None
        self._memory: queue.Queue = queue.Queue()
        self._memory_dlq = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.consumer = "%s-%s" % (socket.gethostname(), uuid.uuid4().hex[:8])
        if redis_url:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("Redis mode requires: pip install redis") from exc
            self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
            try:
                self._redis.xgroup_create(self.STREAM, self.GROUP, id="0", mkstream=True)
            except redis.ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
            for _ in range(workers):
                self._executor.submit(self._redis_worker)

    # 返回实际使用的队列后端名称，供健康检查和任务响应展示。
    @property
    def backend(self) -> str:
        return "redis-streams" if self._redis else "memory-acked"

    # 将业务载荷包装为含消息标识和尝试次数的信封，再投递到选定后端。
    def submit(self, payload: Dict[str, Any], message_id: str = "") -> str:
        envelope = {
            "message_id": message_id or str(payload.get("task_id") or uuid.uuid4()),
            "attempt": 0,
            "payload": payload,
            "submitted_at": time.time(),
        }
        if self._redis:
            self._redis.xadd(self.STREAM, {"envelope": json.dumps(envelope, ensure_ascii=False)})
        else:
            self._executor.submit(self._deliver, envelope)
        return envelope["message_id"]

    # 增加尝试次数并调用处理器；永久错误直接进死信，其余失败按策略重投。
    def _deliver(self, envelope: Dict[str, Any]) -> bool:
        envelope["attempt"] = int(envelope.get("attempt", 0)) + 1
        try:
            self.handler(envelope["payload"])
            return True
        except QueueLeaseBusy:
            raise
        except PermanentTaskError as exc:
            self._dead_letter(envelope, str(exc))
            return False
        except Exception as exc:
            if envelope["attempt"] >= self.max_attempts:
                self._dead_letter(envelope, str(exc))
            # Redis 重试写入新消息；原消息随后 ACK，避免同时保留两个有效投递入口。
            elif self._redis:
                self._redis.xadd(self.STREAM, {
                    "envelope": json.dumps(envelope, ensure_ascii=False)
                })
            else:
                # 内存后端用指数退避重试，最长等待 10 秒；定时器不阻塞当前 Worker。
                delay = min(2 ** (envelope["attempt"] - 1), 10)
                timer = threading.Timer(delay, self._submit_memory, args=(envelope,))
                timer.daemon = True
                timer.start()
            return False

    # 延迟重试到期后重新提交线程池；队列关闭后不再提交。
    def _submit_memory(self, envelope: Dict[str, Any]) -> None:
        if not self._stop.is_set():
            self._executor.submit(self._deliver, envelope)

    # 持续领取消费组消息，处理完成或安全转移后才确认原消息。
    def _redis_worker(self) -> None:
        while not self._stop.is_set():
            self._reclaim_stale()
            messages = self._redis.xreadgroup(
                self.GROUP, self.consumer, {self.STREAM: ">"}, count=1, block=1000
            )
            for _stream, entries in messages:
                for redis_id, fields in entries:
                    try:
                        envelope = json.loads(fields["envelope"])
                    except Exception as exc:
                        envelope = {
                            "message_id": redis_id, "attempt": self.max_attempts,
                            "payload": {}, "submitted_at": time.time(),
                        }
                        self._dead_letter(envelope, "invalid queue envelope: %s" % exc)
                        self._redis.xack(self.STREAM, self.GROUP, redis_id)
                        continue
                    try:
                        # 只有业务完成、重新入队或写入死信后才可确认；基础设施异常会保留 pending。
                        self._deliver(envelope)
                        # ACK only after work completed or was safely requeued/DLQed.
                        self._redis.xack(self.STREAM, self.GROUP, redis_id)
                    except Exception:
                        # Infrastructure failure: leave pending for lease recovery.
                        continue

    # 尝试认领租约超时的 Redis 待处理消息，恢复失联 Worker 遗留任务。
    def _reclaim_stale(self) -> None:
        try:
            result = self._redis.xautoclaim(
                self.STREAM, self.GROUP, self.consumer,
                min_idle_time=self.lease_seconds * 1000, start_id="0-0", count=10,
            )
            entries = result[1] if len(result) > 1 else []
            for redis_id, fields in entries:
                envelope = json.loads(fields["envelope"])
                self._deliver(envelope)
                self._redis.xack(self.STREAM, self.GROUP, redis_id)
        except Exception:
            # Redis versions without XAUTOCLAIM still process new entries.
            return

    # 保存终止重试的消息与错误，并通知服务层更新任务状态。
    def _dead_letter(self, envelope: Dict[str, Any], error: str) -> None:
        item = {**envelope, "error": error[:2000], "failed_at": time.time()}
        if self._redis:
            self._redis.xadd(self.DLQ, {"envelope": json.dumps(item, ensure_ascii=False)})
        else:
            with self._lock:
                self._memory_dlq.append(item)
        if self.on_dead_letter:
            self.on_dead_letter(envelope.get("payload") or {}, item["error"])

    # 读取最近的死信消息，统一 Redis 与内存后端的输出格式。
    def dead_letters(self, limit: int = 100) -> list:
        if self._redis:
            rows = self._redis.xrevrange(self.DLQ, count=max(1, min(limit, 500)))
            return [json.loads(fields["envelope"]) for _id, fields in rows]
        with self._lock:
            return list(reversed(self._memory_dlq[-limit:]))

    # 按消息标识找到死信载荷，重新投递并重置尝试次数。
    def replay_dead_letter(self, message_id: str) -> bool:
        for item in self.dead_letters(500):
            if item.get("message_id") == message_id:
                payload = item.get("payload") or {}
                self.submit(payload, message_id=message_id)
                return True
        return False

    def close(self, wait: bool = True) -> None:
        self._stop.set()
        self._executor.shutdown(wait=wait, cancel_futures=not wait)
