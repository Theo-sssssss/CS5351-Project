# SQLite 持久化后端：保存任务、执行轨迹、检查点、记忆、评测版本和租户授权。
# 通过参数化 SQL 传值，并在写入操作中维护业务状态与相关记录。

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .models import ReviewReport, TaskState, TraceEvent
from .workbench_store import WorkbenchStore


# 生成带 UTC 时区的当前时间，统一持久化时间格式。
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# SQLite 存储实现，承接业务状态、检查点与版本数据。
class TaskStore(WorkbenchStore):
    # 保存 SQLite 路径并创建写锁，初始化数据库结构以兼容已有任务。
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._init()
        self.init_workbench()

    # 建立数据库连接，并设置本后端使用的行结果格式。
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # 创建所需表和索引，并执行已有数据库的兼容性初始化。
    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS review_leases "
                         "(task_id TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    pull_request INTEGER,
                    input_json TEXT NOT NULL,
                    report_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS failure_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    skill_name TEXT NOT NULL DEFAULT 'llm-review',
                    category TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS skill_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    score REAL NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0,
                    parent_version INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(skill_name, version)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS installations (
                    installation_id INTEGER PRIMARY KEY,
                    account_login TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS evaluation_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    split TEXT NOT NULL,
                    diff TEXT NOT NULL,
                    expected_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS evolution_runs (
                    id TEXT PRIMARY KEY,
                    skill_name TEXT NOT NULL,
                    candidate_version INTEGER NOT NULL,
                    baseline_version INTEGER,
                    decision TEXT NOT NULL,
                    candidate_score REAL NOT NULL,
                    baseline_score REAL NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS skill_artifact_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    skill_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    artifact_json TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    score REAL NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0,
                    parent_version INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, skill_name, version)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS skill_evolution_runs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    skill_name TEXT NOT NULL,
                    candidate_version INTEGER NOT NULL,
                    baseline_version INTEGER,
                    decision TEXT NOT NULL,
                    candidate_score REAL NOT NULL,
                    baseline_score REAL NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            self._ensure_column(
                conn, "skill_artifact_versions", "tenant_id", "TEXT NOT NULL DEFAULT 'default'"
            )
            self._ensure_column(
                conn, "skill_evolution_runs", "tenant_id", "TEXT NOT NULL DEFAULT 'default'"
            )
            self._ensure_column(conn, "tasks", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
            self._ensure_column(conn, "tasks", "cancel_requested", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "installations", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
            self._ensure_column(
                conn, "failure_cases", "skill_name", "TEXT NOT NULL DEFAULT 'llm-review'"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_failure_cases_skill_unresolved "
                "ON failure_cases(skill_name, resolved, id)"
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS checkpoints (
                    task_id TEXT NOT NULL,
                    node TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 1,
                    state_json TEXT NOT NULL,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, node),
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS task_payloads (
                    task_id TEXT PRIMARY KEY,
                    diff TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS agent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    task_id TEXT,
                    received_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS memberships (
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    PRIMARY KEY(user_id, tenant_id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS repository_grants (
                    tenant_id TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    auto_fix INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(tenant_id, repository)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS deployments (
                    tenant_id TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    stable_version INTEGER,
                    candidate_version INTEGER,
                    canary_percent INTEGER NOT NULL DEFAULT 0,
                    shadow_percent INTEGER NOT NULL DEFAULT 0,
                    max_error_rate REAL NOT NULL DEFAULT 0.1,
                    min_samples INTEGER NOT NULL DEFAULT 20,
                    status TEXT NOT NULL DEFAULT 'stable',
                    samples INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, skill_name)
                )"""
            )
            self._ensure_column(
                conn, "deployments", "max_disagreement_rate",
                "REAL NOT NULL DEFAULT 0.2"
            )
            self._ensure_column(
                conn, "deployments", "auto_promote", "INTEGER NOT NULL DEFAULT 0"
            )
            self._ensure_column(
                conn, "deployments", "shadow_samples", "INTEGER NOT NULL DEFAULT 0"
            )
            self._ensure_column(
                conn, "deployments", "disagreements", "INTEGER NOT NULL DEFAULT 0"
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS release_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    lane TEXT NOT NULL,
                    primary_json TEXT NOT NULL,
                    candidate_json TEXT,
                    disagreement REAL NOT NULL,
                    candidate_failed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    alert_key TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, alert_key, status)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS agent_memories (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    task_id TEXT NOT NULL DEFAULT '',
                    agent TEXT NOT NULL DEFAULT '',
                    scope TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_tenant_created ON tasks(tenant_id, created_at)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_memories_lookup "
                "ON agent_memories(tenant_id, repository, scope, created_at)"
            )

    # 检查旧表是否已有指定列，仅在缺失时补列以兼容历史数据库。
    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table).fetchall()}
        if column not in columns:
            conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, declaration))

    # 创建初始任务记录，将输入元信息与租户绑定。
    def create(
        self, task_id: str, repository: str, pull_request: Optional[int],
        payload: Dict[str, Any], tenant_id: str = "default",
    ) -> None:
        now = utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks(id,state,repository,pull_request,input_json,report_json,error,"
                "created_at,updated_at,tenant_id,cancel_requested) "
                "VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, 0)",
                (task_id, TaskState.PENDING.value, repository, pull_request,
                 json.dumps(payload), now, now, tenant_id),
            )

    @contextmanager
    def review_lock(self, task_id):
        import uuid
        owner = uuid.uuid4().hex
        now = time.time()
        with self._lock, self._connect() as conn:
            acquired = conn.execute(
                "INSERT INTO review_leases VALUES (?,?,?) ON CONFLICT(task_id) DO UPDATE "
                "SET owner=excluded.owner,expires=excluded.expires WHERE review_leases.expires<?",
                (task_id, owner, now + 30, now),
            ).rowcount
        if not acquired:
            yield False
            return
        stopped = threading.Event()

        def heartbeat():
            while not stopped.wait(5):
                try:
                    with self._lock, self._connect() as conn:
                        conn.execute("UPDATE review_leases SET expires=? WHERE task_id=? AND owner=?",
                                     (time.time() + 30, task_id, owner))
                except sqlite3.OperationalError:
                    continue

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            yield True
        finally:
            stopped.set()
            thread.join()
            with self._lock, self._connect() as conn:
                conn.execute("DELETE FROM review_leases WHERE task_id=? AND owner=?", (task_id, owner))

    # 同时更新任务状态与轨迹事件，保持进度记录可追溯。
    def transition(self, task_id: str, event: TraceEvent) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state = ?, updated_at = ? WHERE id = ?",
                (event.state.value, event.created_at, task_id),
            )
            conn.execute(
                "INSERT INTO trace_events(task_id, step, state, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 将任务置为成功，保存最终报告并追加结束轨迹。
    def succeed(self, task_id: str, report: ReviewReport, event: TraceEvent) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state = ?, report_json = ?, updated_at = ?, error=NULL WHERE id = ?",
                (TaskState.SUCCESS.value, json.dumps(report.to_dict(), ensure_ascii=False), event.created_at, task_id),
            )
            conn.execute(
                "INSERT INTO trace_events(task_id, step, state, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 将任务置为失败，保存错误信息并追加失败轨迹。
    def fail(self, task_id: str, error: str, event: TraceEvent) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state = ?, error = ?, updated_at = ? WHERE id = ?",
                (TaskState.FAILED.value, error[:2000], event.created_at, task_id),
            )
            conn.execute(
                "INSERT INTO trace_events(task_id, step, state, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 按任务标识及可选租户查询任务，解码输入、报告和附属执行记录。
    def get(self, task_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            if tenant_id is None:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND tenant_id = ?", (task_id, tenant_id)
                ).fetchone()
            if row is None:
                return None
            events = conn.execute(
                "SELECT step, state, message, created_at FROM trace_events WHERE task_id = ? ORDER BY id", (task_id,)
            ).fetchall()
            messages = conn.execute(
                "SELECT sender,recipient,kind,correlation_id,content_json,created_at "
                "FROM agent_messages WHERE task_id=? ORDER BY id", (task_id,)
            ).fetchall()
        value = dict(row)
        value["input"] = json.loads(value.pop("input_json"))
        report_json = value.pop("report_json")
        value["report"] = json.loads(report_json) if report_json else None
        value["trace"] = [dict(item) for item in events]
        value["collaboration"] = []
        for message in messages:
            item = dict(message)
            item["content"] = json.loads(item.pop("content_json"))
            value["collaboration"].append(item)
        return value

    # 追加一条角色间消息，记录发送方、接收方、消息类型和内容。
    def record_agent_message(self, task_id: str, message: Dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_messages(task_id,sender,recipient,kind,correlation_id,"
                "content_json,created_at) VALUES (?,?,?,?,?,?,?)",
                (task_id, message["sender"], message["recipient"], message["kind"],
                 message.get("correlation_id", ""),
                 json.dumps(message.get("content", {}), ensure_ascii=False), utc_now()),
            )

    # 按记忆标识保存或更新内容及过期信息，返回规范化记录。
    def save_agent_memory(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_memories(id,tenant_id,repository,task_id,agent,scope,kind,"
                "content,keywords_json,metadata_json,importance,created_at,expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "importance=MAX(agent_memories.importance,excluded.importance),"
                "expires_at=excluded.expires_at",
                (
                    memory["id"], memory["tenant_id"], memory["repository"],
                    memory.get("task_id", ""), memory.get("agent", ""), memory["scope"],
                    memory["kind"], memory["content"],
                    json.dumps(memory.get("keywords", []), ensure_ascii=False),
                    json.dumps(memory.get("metadata", {}), ensure_ascii=False),
                    float(memory.get("importance", 0.5)), memory["created_at"],
                    memory.get("expires_at"),
                ),
            )
            row = conn.execute(
                "SELECT * FROM agent_memories WHERE id=?", (memory["id"],)
            ).fetchone()
        return self._memory_from_row(row)

    # 在租户、仓库和作用域范围内查询记忆，并排除过期条目。
    def list_agent_memories(
        self, tenant_id: str, repository: str, scopes: tuple,
        limit: int = 100,
    ) -> list:
        placeholders = ",".join("?" for _ in scopes)
        params = [tenant_id, repository, *scopes, utc_now(), max(1, min(limit, 500))]
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_memories WHERE tenant_id=? AND repository=? "
                "AND scope IN (%s) AND (expires_at IS NULL OR expires_at>?) "
                "ORDER BY importance DESC,created_at DESC LIMIT ?" % placeholders,
                params,
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    # 按提供的任务和作用域等条件删除记忆，返回删除数量。
    def delete_agent_memories(self, task_id: str = "", scope: str = "") -> int:
        clauses = []
        params = []
        if task_id:
            clauses.append("task_id=?")
            params.append(task_id)
        if scope:
            clauses.append("scope=?")
            params.append(scope)
        if not clauses:
            raise ValueError("memory deletion requires task_id or scope")
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_memories WHERE " + " AND ".join(clauses), params
            )
            return cursor.rowcount

    # 删除到期的记忆记录，避免过期观察参与后续召回。
    def purge_expired_agent_memories(self) -> int:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_memories WHERE expires_at IS NOT NULL AND expires_at<=?",
                (utc_now(),),
            )
            return cursor.rowcount

    # 将数据库行中的 JSON 字段解码为记忆对象。
    @staticmethod
    def _memory_from_row(row) -> Dict[str, Any]:
        value = dict(row)
        value["keywords"] = json.loads(value.pop("keywords_json"))
        value["metadata"] = json.loads(value.pop("metadata_json"))
        return value

    # 按可选租户读取最近任务，限制返回数量供列表展示。
    def list_tasks(self, limit: int = 50, tenant_id: Optional[str] = None) -> list:
        with self._connect() as conn:
            if tenant_id is None:
                rows = conn.execute(
                    "SELECT id,state,repository,pull_request,error,created_at,updated_at,tenant_id "
                    "FROM tasks WHERE json_extract(input_json,'$.job_type') IS NULL ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(limit, 200)),)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id,state,repository,pull_request,error,created_at,updated_at,tenant_id "
                    "FROM tasks WHERE tenant_id=? AND json_extract(input_json,'$.job_type') IS NULL "
                    "ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, max(1, min(limit, 200))),
                ).fetchall()
        return [dict(item) for item in rows]

    def interrupted_tasks(self):
        with self._connect() as conn:
            return [row["id"] for row in conn.execute(
                "SELECT id FROM tasks WHERE state IN ('PENDING','PLANNING','EXECUTING','REVIEWING') "
                "AND (json_extract(input_json,'$.review_engine') IS NOT NULL "
                "OR json_extract(input_json,'$.job_type')='evolution') ORDER BY created_at"
            )]

    # 将审查反馈或执行错误保存为待处理案例，供后续演进消费。
    def record_failure_case(
        self, task_id: str, category: str, payload: Dict[str, Any],
        skill_name: str = "llm-review",
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO failure_cases(task_id,skill_name,category,payload_json,created_at) "
                "VALUES (?,?,?,?,?)",
                (task_id, skill_name, category, json.dumps(payload, ensure_ascii=False), utc_now()),
            )

    # 按解决状态、租户和可选 Skill 查询反馈案例，避免跨租户或跨领域学习。
    def list_failure_cases(
        self, unresolved_only: bool = False, limit: int = 100,
        tenant_id: Optional[str] = None, skill_name: Optional[str] = None,
    ) -> list:
        query = "SELECT f.* FROM failure_cases f"
        params = []
        clauses = []
        if tenant_id is not None:
            query += " JOIN tasks t ON t.id=f.task_id"
            clauses.append("t.tenant_id = ?")
            params.append(tenant_id)
        if unresolved_only:
            clauses.append("f.resolved = 0")
        if skill_name is not None:
            clauses.append("f.skill_name = ?")
            params.append(skill_name)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY f.id DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            values.append(item)
        return values

    # 读取指定任务在给定租户范围内的反馈，供任务详情展示。
    def list_task_failure_cases(
        self, task_id: str, tenant_id: Optional[str] = None,
    ) -> list:
        query = "SELECT f.* FROM failure_cases f"
        params = []
        if tenant_id is not None:
            query += " JOIN tasks t ON t.id=f.task_id"
            query += " WHERE f.task_id=? AND t.tenant_id=?"
            params.extend([task_id, tenant_id])
        else:
            query += " WHERE f.task_id=?"
            params.append(task_id)
        query += " ORDER BY f.id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            values.append(item)
        return values

    # 把已经用于成功演进的案例标记为已解决。
    def resolve_failure_cases(self, case_ids: list) -> None:
        ids = [int(value) for value in case_ids]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE failure_cases SET resolved = 1 WHERE id IN (%s)" % placeholders,
                ids,
            )

    # 保存不可变评测案例；相同输入可幂等返回，冲突内容拒绝覆盖。
    def save_evaluation_case(
        self, name: str, split: str, diff: str, expected: list,
        source: str = "manual", active: bool = True,
    ) -> Dict[str, Any]:
        expected_json = json.dumps(expected, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM evaluation_cases WHERE name = ?", (name,)
            ).fetchone()
            if existing is not None:
                if (
                    existing["split"] != split
                    or existing["diff"] != diff
                    or json.loads(existing["expected_json"]) != expected
                ):
                    raise ValueError(
                        "evaluation case names are immutable; use a new name for revised content"
                    )
                row = existing
            else:
                conn.execute(
                    "INSERT INTO evaluation_cases(name,split,diff,expected_json,source,active,created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (name, split, diff, expected_json, source, int(active), utc_now()),
                )
                row = conn.execute(
                    "SELECT * FROM evaluation_cases WHERE name = ?", (name,)
                ).fetchone()
        value = dict(row)
        value["expected"] = json.loads(value.pop("expected_json"))
        value["active"] = bool(value["active"])
        return value

    # 按数据划分和启用状态读取案例，限制单次回放规模。
    def list_evaluation_cases(
        self, split: Optional[str] = None, active_only: bool = True, limit: int = 100,
    ) -> list:
        clauses = []
        params = []
        if split:
            clauses.append("split = ?")
            params.append(split)
        if active_only:
            clauses.append("active = 1")
        query = "SELECT * FROM evaluation_cases"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["expected"] = json.loads(value.pop("expected_json"))
            value["active"] = bool(value["active"])
            values.append(value)
        return values

    # 保存提示词候选的基线、分数、门禁决策和复现信息。
    def save_evolution_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO evolution_runs(id,skill_name,candidate_version,baseline_version,decision,"
                "candidate_score,baseline_score,metrics_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    run["id"], run["skill_name"], run["candidate_version"], run.get("baseline_version"),
                    run["decision"], run["candidate_score"], run["baseline_score"],
                    json.dumps(run["metrics"], ensure_ascii=False), run["created_at"],
                ),
            )
        return run

    # 读取最近的提示词演进记录，并解码指标详情。
    def list_evolution_runs(self, limit: int = 50) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evolution_runs ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["metrics"] = json.loads(value.pop("metrics_json"))
            values.append(value)
        return values

    # 更新已有演进记录的决策与指标，补充结构化候选信息。
    def update_evolution_run(self, run_id: str, decision: str, metrics: Dict[str, Any]) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE evolution_runs SET decision = ?, metrics_json = ? WHERE id = ?",
                (decision, json.dumps(metrics, ensure_ascii=False), run_id),
            )
            return cursor.rowcount == 1

    # 为提示词分配版本号并保存，必要时替换同 Skill 的活动版本。
    def save_skill_version(self, skill_name: str, prompt: str, score: float, activate: bool = False) -> Dict[str, Any]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM skill_versions WHERE skill_name = ?", (skill_name,)
            ).fetchone()
            version = int(row["version"]) + 1
            parent = self.get_active_skill_version(skill_name)
            if activate:
                conn.execute("UPDATE skill_versions SET active = 0 WHERE skill_name = ?", (skill_name,))
            conn.execute(
                "INSERT INTO skill_versions(skill_name, version, prompt, score, active, parent_version, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (skill_name, version, prompt, score, int(activate), parent["version"] if parent else None, utc_now()),
            )
        return {"skill_name": skill_name, "version": version, "score": score, "active": activate}

    # 查找指定 Skill 当前启用的提示词版本。
    def get_active_skill_version(self, skill_name: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM skill_versions WHERE skill_name = ? AND active = 1 ORDER BY version DESC LIMIT 1",
                (skill_name,),
            ).fetchone()
        return dict(row) if row else None

    # 列出指定 Skill 的提示词历史，供查看和回滚。
    def list_skill_versions(self, skill_name: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_versions WHERE skill_name = ? ORDER BY version DESC", (skill_name,)
            ).fetchall()
        return [dict(item) for item in rows]

    # 确认目标版本存在后切换活动标记，避免激活不存在的版本。
    def activate_skill_version(self, skill_name: str, version: int) -> bool:
        with self._lock, self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM skill_versions WHERE skill_name = ? AND version = ?", (skill_name, version)
            ).fetchone()
            if not exists:
                return False
            conn.execute("UPDATE skill_versions SET active = 0 WHERE skill_name = ?", (skill_name,))
            conn.execute(
                "UPDATE skill_versions SET active = 1 WHERE skill_name = ? AND version = ?", (skill_name, version)
            )
        return True

    # 按租户和 Skill 保存完整制品及内容指纹，分配版本并可设为活动状态。
    def save_skill_artifact(
        self, skill_name: str, artifact: Dict[str, Any], score: float,
        activate: bool = False, tenant_id: str = "default",
    ) -> Dict[str, Any]:
        artifact_json = json.dumps(
            artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        artifact_sha256 = hashlib.sha256(artifact_json.encode("utf-8")).hexdigest()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version),0) AS version FROM skill_artifact_versions "
                "WHERE tenant_id=? AND skill_name=?", (tenant_id, skill_name),
            ).fetchone()
            version = int(row["version"]) + 1
            parent = conn.execute(
                "SELECT version FROM skill_artifact_versions WHERE tenant_id=? AND skill_name=? "
                "AND active=1 ORDER BY version DESC LIMIT 1", (tenant_id, skill_name),
            ).fetchone()
            if activate:
                conn.execute(
                    "UPDATE skill_artifact_versions SET active=0 WHERE tenant_id=? AND skill_name=?",
                    (tenant_id, skill_name),
                )
            created_at = utc_now()
            conn.execute(
                "INSERT INTO skill_artifact_versions(tenant_id,skill_name,version,artifact_json,"
                "artifact_sha256,score,active,parent_version,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (tenant_id, skill_name, version, artifact_json, artifact_sha256, float(score),
                 int(activate), parent["version"] if parent else None, created_at),
            )
        return {
            "tenant_id": tenant_id, "skill_name": skill_name, "version": version, "score": float(score),
            "active": activate, "parent_version": parent["version"] if parent else None,
            "artifact_sha256": artifact_sha256, "created_at": created_at,
        }

    # 解码数据库中的 Skill 制品与附属元数据。
    @staticmethod
    def _decode_skill_artifact(row) -> Dict[str, Any]:
        value = dict(row)
        value["artifact"] = json.loads(value.pop("artifact_json"))
        value["active"] = bool(value["active"])
        return value

    # 读取指定租户、指定 Skill 的当前活动制品。
    def get_active_skill_artifact(
        self, skill_name: str, tenant_id: str = "default",
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM skill_artifact_versions WHERE tenant_id=? AND skill_name=? "
                "AND active=1 ORDER BY version DESC LIMIT 1", (tenant_id, skill_name),
            ).fetchone()
        return self._decode_skill_artifact(row) if row else None

    # 列出当前租户已激活的全部 Skill 制品，供覆盖磁盘版本。
    def list_active_skill_artifacts(self, tenant_id: str = "default") -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_artifact_versions WHERE tenant_id=? AND active=1 "
                "ORDER BY skill_name", (tenant_id,)
            ).fetchall()
        return [self._decode_skill_artifact(row) for row in rows]

    # 读取某租户中指定 Skill 的版本历史。
    def list_skill_artifact_versions(
        self, skill_name: str, tenant_id: str = "default",
    ) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_artifact_versions WHERE tenant_id=? AND skill_name=? "
                "ORDER BY version DESC", (tenant_id, skill_name),
            ).fetchall()
        return [self._decode_skill_artifact(row) for row in rows]

    # 在租户范围内切换 Skill 活动制品，避免影响其他租户。
    def activate_skill_artifact(
        self, skill_name: str, version: int, tenant_id: str = "default",
    ) -> bool:
        with self._lock, self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM skill_artifact_versions v WHERE v.tenant_id=? "
                "AND v.skill_name=? AND v.version=? AND (v.active=1 OR EXISTS ("
                "SELECT 1 FROM skill_evolution_runs r WHERE r.tenant_id=v.tenant_id "
                "AND r.skill_name=v.skill_name AND r.candidate_version=v.version "
                "AND r.decision='activated'))",
                (tenant_id, skill_name, version),
            ).fetchone()
            if not exists:
                return False
            conn.execute(
                "UPDATE skill_artifact_versions SET active=0 WHERE tenant_id=? AND skill_name=?",
                (tenant_id, skill_name),
            )
            conn.execute(
                "UPDATE skill_artifact_versions SET active=1 WHERE tenant_id=? AND skill_name=? "
                "AND version=?", (tenant_id, skill_name, version),
            )
        return True

    # 保存制品演进的候选版本、对比指标和最终决策。
    def save_skill_evolution_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO skill_evolution_runs(id,tenant_id,skill_name,candidate_version,baseline_version,"
                "decision,candidate_score,baseline_score,metrics_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run["id"], run.get("tenant_id", "default"), run["skill_name"], run["candidate_version"],
                 run.get("baseline_version"), run["decision"], run["candidate_score"],
                 run["baseline_score"], json.dumps(run["metrics"], ensure_ascii=False),
                 run["created_at"]),
            )
        return run

    # 按租户及筛选条件读取最近的制品演进记录。
    def list_skill_evolution_runs(
        self, limit: int = 50, tenant_id: Optional[str] = None,
    ) -> list:
        with self._connect() as conn:
            if tenant_id is None:
                rows = conn.execute(
                    "SELECT * FROM skill_evolution_runs ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(limit, 200)),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skill_evolution_runs WHERE tenant_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, max(1, min(limit, 200))),
                ).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["metrics"] = json.loads(value.pop("metrics_json"))
            values.append(value)
        return values

    # 保存 GitHub App 安装与租户之间的映射。
    def save_installation(
        self, installation_id: int, account_login: str, tenant_id: str = "default"
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO installations"
                "(installation_id,account_login,created_at,tenant_id) VALUES (?, ?, ?, ?)",
                (installation_id, account_login, utc_now(), tenant_id),
            )

    # 根据安装标识解析所属租户，供 Webhook 路由使用。
    def installation_tenant(self, installation_id: int) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tenant_id FROM installations WHERE installation_id=?", (installation_id,)
            ).fetchone()
        return str(row["tenant_id"]) if row else None

    # 按任务与节点写入输出、状态、尝试次数和错误，作为恢复依据。
    def save_checkpoint(
        self, task_id: str, node: str, state: Dict[str, Any], status: str = "completed",
        attempt: int = 1, error: str = "",
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO checkpoints(task_id,node,status,attempt,state_json,error,updated_at) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(task_id,node) DO UPDATE SET "
                "status=excluded.status,attempt=excluded.attempt,state_json=excluded.state_json,"
                "error=excluded.error,updated_at=excluded.updated_at",
                (task_id, node, status, attempt, json.dumps(state, ensure_ascii=False),
                 error[:2000] or None, utc_now()),
            )

    # 读取任务的全部节点检查点，并还原保存的状态字典。
    def load_checkpoints(self, task_id: str) -> Dict[str, Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT node,status,attempt,state_json,error,updated_at FROM checkpoints "
                "WHERE task_id=? ORDER BY updated_at", (task_id,)
            ).fetchall()
        result = {}
        for row in rows:
            item = dict(row)
            item["state"] = json.loads(item.pop("state_json"))
            result[item.pop("node")] = item
        return result

    # 独立保存原始 Diff，供异步执行和任务恢复读取。
    def save_task_payload(self, task_id: str, diff: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO task_payloads(task_id,diff,created_at) VALUES (?,?,?)",
                (task_id, diff, utc_now()),
            )

    # 合并任务输入元信息，保留未被本次更新覆盖的字段。
    def update_task_input(self, task_id: str, updates: Dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT input_json FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not row:
                raise ValueError("task not found")
            value = json.loads(row["input_json"])
            value.update(updates)
            conn.execute(
                "UPDATE tasks SET input_json=?,updated_at=? WHERE id=?",
                (json.dumps(value, ensure_ascii=False), utc_now(), task_id),
            )

    # 读取原始 Diff；不存在时返回空值，由调用方决定是否重取或失败。
    def get_task_payload(self, task_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT diff FROM task_payloads WHERE task_id=?", (task_id,)
            ).fetchone()
        return str(row["diff"]) if row else None

    # 为符合条件的任务设置取消请求，由运行时在节点边界响应。
    def request_cancel(self, task_id: str, tenant_id: Optional[str] = None) -> bool:
        query = "UPDATE tasks SET cancel_requested=1,updated_at=? WHERE id=? AND state NOT IN ('SUCCESS','FAILED','CANCELLED')"
        params = [utc_now(), task_id]
        if tenant_id is not None:
            query += " AND tenant_id=?"
            params.append(tenant_id)
        with self._lock, self._connect() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0

    # 读取任务是否已请求取消或已经进入取消状态。
    def is_cancelled(self, task_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT cancel_requested FROM tasks WHERE id=?", (task_id,)).fetchone()
        return bool(row and row["cancel_requested"])

    # 记录取消终态并追加轨迹，使任务详情反映取消结果。
    def cancel(self, task_id: str, event: TraceEvent) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state=?,updated_at=? WHERE id=?",
                (TaskState.CANCELLED.value, event.created_at, task_id),
            )
            conn.execute(
                "INSERT INTO trace_events(task_id,step,state,message,created_at) VALUES (?,?,?,?,?)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 尝试占用 delivery ID 并绑定载荷指纹，识别重复事件及同 ID 内容冲突。
    def claim_webhook(
        self, delivery_id: str, tenant_id: str, event_type: str, payload_sha256: str,
    ) -> bool:
        if not delivery_id:
            raise ValueError("X-GitHub-Delivery is required")
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO webhook_deliveries"
                    "(delivery_id,tenant_id,event_type,payload_sha256,received_at) VALUES (?,?,?,?,?)",
                    (delivery_id, tenant_id, event_type, payload_sha256, utc_now()),
                )
                return True
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT payload_sha256 FROM webhook_deliveries WHERE delivery_id=?",
                    (delivery_id,),
                ).fetchone()
                if row and row["payload_sha256"] != payload_sha256:
                    raise ValueError("delivery id was already used with a different payload")
                return False

    # 将已处理的 Webhook 关联到任务，供重复投递返回已有任务标识。
    def complete_webhook(self, delivery_id: str, task_id: Optional[str]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE webhook_deliveries SET task_id=? WHERE delivery_id=?",
                (task_id, delivery_id),
            )

    # 查询已接收事件记录，用于幂等响应和追踪任务。
    def get_webhook(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM webhook_deliveries WHERE delivery_id=?", (delivery_id,)
            ).fetchone()
        return dict(row) if row else None

    # 创建用户及租户角色关系，已有同名用户保留原凭据。
    def create_user(
        self, user_id: str, username: str, password_hash: str,
        tenant_id: str, role: str,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(id,username,password_hash,created_at) VALUES (?,?,?,?)",
                (user_id, username, password_hash, utc_now()),
            )
            row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            conn.execute(
                "INSERT INTO memberships(user_id,tenant_id,role) VALUES (?,?,?) "
                "ON CONFLICT(user_id,tenant_id) DO UPDATE SET role=excluded.role",
                (row["id"], tenant_id, role),
            )

    # 按用户名读取账号状态、密码摘要及租户成员关系。
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id,username,password_hash,active FROM users WHERE username=?", (username,)
            ).fetchone()
            if not row:
                return None
            memberships = conn.execute(
                "SELECT tenant_id,role FROM memberships WHERE user_id=?", (row["id"],)
            ).fetchall()
        value = dict(row)
        value["memberships"] = [dict(item) for item in memberships]
        return value

    # 保存租户对仓库的访问授权及是否允许自动修复。
    def grant_repository(self, tenant_id: str, repository: str, auto_fix: bool = False) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO repository_grants(tenant_id,repository,auto_fix) VALUES (?,?,?) "
                "ON CONFLICT(tenant_id,repository) DO UPDATE SET auto_fix=excluded.auto_fix",
                (tenant_id, repository, int(auto_fix)),
            )

    # 检查租户的仓库授权；修复场景额外检查自动修复开关。
    def repository_allowed(
        self, tenant_id: str, repository: str, require_auto_fix: bool = False,
    ) -> bool:
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM repository_grants WHERE tenant_id=?", (tenant_id,)
            ).fetchone()["n"]
            row = conn.execute(
                "SELECT auto_fix FROM repository_grants WHERE tenant_id=? AND repository=?",
                (tenant_id, repository),
            ).fetchone()
        if total == 0:
            return True
        return bool(row and (not require_auto_fix or row["auto_fix"]))

    # 追加管理操作审计记录，保留操作者、动作和目标上下文。
    def audit(
        self, tenant_id: str, actor: str, action: str, resource: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log(tenant_id,actor,action,resource,detail_json,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (tenant_id, actor, action, resource,
                 json.dumps(detail or {}, ensure_ascii=False), utc_now()),
            )

    # 按租户读取最近审计记录，供管理员或审计员查看。
    def list_audit(self, tenant_id: str, limit: int = 100) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT actor,action,resource,detail_json,created_at FROM audit_log "
                "WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
                (tenant_id, max(1, min(limit, 500))),
            ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["detail"] = json.loads(item.pop("detail_json"))
            values.append(item)
        return values

    # 保存某租户的 Skill 灰度比例、影子模式与错误预算配置。
    def save_deployment(self, tenant_id: str, skill_name: str, config: Dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO deployments(tenant_id,skill_name,stable_version,candidate_version,"
                "canary_percent,shadow_percent,max_error_rate,min_samples,status,samples,errors,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,0,0,?) ON CONFLICT(tenant_id,skill_name) DO UPDATE SET "
                "stable_version=excluded.stable_version,candidate_version=excluded.candidate_version,"
                "canary_percent=excluded.canary_percent,shadow_percent=excluded.shadow_percent,"
                "max_error_rate=excluded.max_error_rate,min_samples=excluded.min_samples,"
                "status=excluded.status,samples=0,errors=0,updated_at=excluded.updated_at",
                (tenant_id, skill_name, config.get("stable_version"), config.get("candidate_version"),
                 int(config.get("canary_percent", 0)), int(config.get("shadow_percent", 0)),
                 float(config.get("max_error_rate", .1)), int(config.get("min_samples", 20)),
                 config.get("status", "running"), utc_now()),
            )
            conn.execute(
                "UPDATE deployments SET max_disagreement_rate=?,auto_promote=?,"
                "shadow_samples=0,disagreements=0 WHERE tenant_id=? AND skill_name=?",
                (float(config.get("max_disagreement_rate", .2)),
                 int(bool(config.get("auto_promote", False))), tenant_id, skill_name),
            )

    # 查询租户当前的 Skill 发布状态与累计统计。
    def get_deployment(self, tenant_id: str, skill_name: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM deployments WHERE tenant_id=? AND skill_name=?",
                (tenant_id, skill_name),
            ).fetchone()
        return dict(row) if row else None

    # 累计指定发布分组的成功和失败，更新错误预算及回滚状态。
    def record_deployment_result(
        self, tenant_id: str, skill_name: str, failed: bool,
    ) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE deployments SET samples=samples+1,errors=errors+?,updated_at=? "
                "WHERE tenant_id=? AND skill_name=?",
                (int(failed), utc_now(), tenant_id, skill_name),
            )
            row = conn.execute(
                "SELECT * FROM deployments WHERE tenant_id=? AND skill_name=?",
                (tenant_id, skill_name),
            ).fetchone()
            if not row:
                return None
            value = dict(row)
            if (
                value["status"] == "running"
                and value["samples"] >= value["min_samples"]
                and value["errors"] / value["samples"] > value["max_error_rate"]
            ):
                conn.execute(
                    "UPDATE deployments SET status='rolled_back',canary_percent=0,"
                    "shadow_percent=0,updated_at=? WHERE tenant_id=? AND skill_name=?",
                    (utc_now(), tenant_id, skill_name),
                )
                value["status"] = "rolled_back"
        return value

    # 保存稳定与影子运行的对比指标，为后续放量提供依据。
    def record_shadow_observation(
        self, tenant_id: str, skill_name: str, task_id: str, lane: str,
        primary: Dict[str, Any], candidate: Optional[Dict[str, Any]],
        disagreement: float, candidate_failed: bool = False,
    ) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO release_observations(tenant_id,skill_name,task_id,lane,"
                "primary_json,candidate_json,disagreement,candidate_failed,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (tenant_id, skill_name, task_id, lane,
                 json.dumps(primary, ensure_ascii=False),
                 json.dumps(candidate, ensure_ascii=False) if candidate is not None else None,
                 float(disagreement), int(candidate_failed), utc_now()),
            )
            conn.execute(
                "UPDATE deployments SET shadow_samples=shadow_samples+1,"
                "disagreements=disagreements+?,updated_at=? "
                "WHERE tenant_id=? AND skill_name=?",
                (int(disagreement > 0), utc_now(), tenant_id, skill_name),
            )
            row = conn.execute(
                "SELECT * FROM deployments WHERE tenant_id=? AND skill_name=?",
                (tenant_id, skill_name),
            ).fetchone()
            if not row:
                return None
            value = dict(row)
            disagreement_rate = (
                value["disagreements"] / value["shadow_samples"]
                if value["shadow_samples"] else 0.0
            )
            error_rate = value["errors"] / value["samples"] if value["samples"] else 0.0
            if (
                value["status"] == "running" and value["auto_promote"]
                and value["shadow_samples"] >= value["min_samples"]
                and disagreement_rate <= value["max_disagreement_rate"]
                and error_rate <= value["max_error_rate"]
                and not candidate_failed
            ):
                conn.execute(
                    "UPDATE deployments SET status='promoted',stable_version=candidate_version,"
                    "canary_percent=0,shadow_percent=0,updated_at=? "
                    "WHERE tenant_id=? AND skill_name=?",
                    (utc_now(), tenant_id, skill_name),
                )
                value["status"] = "promoted"
        return value

    # 查询租户的发布观察记录，供分析灰度和影子表现。
    def list_release_observations(
        self, tenant_id: str, skill_name: str, limit: int = 100,
    ) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM release_observations WHERE tenant_id=? AND skill_name=? "
                "ORDER BY id DESC LIMIT ?",
                (tenant_id, skill_name, max(1, min(limit, 500))),
            ).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["primary"] = json.loads(item.pop("primary_json"))
            raw = item.pop("candidate_json")
            item["candidate"] = json.loads(raw) if raw else None
            values.append(item)
        return values

    # 按告警键保存告警，记录级别、描述及时间。
    def create_alert(
        self, tenant_id: str, alert_key: str, severity: str, message: str,
    ) -> None:
        now = utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO alerts"
                "(tenant_id,alert_key,severity,message,status,created_at,updated_at) "
                "VALUES (?,?,?,?, 'open',?,?)",
                (tenant_id, alert_key, severity, message[:1000], now, now),
            )

    # 读取租户范围内最近的持久化告警。
    def list_alerts(self, tenant_id: str, limit: int = 100) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
                (tenant_id, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    # 汇总任务状态、近期结果及相关计数，供控制台与告警逻辑使用。
    def dashboard_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        with self._connect() as conn:
            clause = " WHERE json_extract(input_json,'$.job_type') IS NULL"
            if tenant_id is not None:
                clause += " AND tenant_id=?"
            params = (tenant_id,) if tenant_id is not None else ()
            total = conn.execute("SELECT COUNT(*) AS n FROM tasks" + clause, params).fetchone()["n"]
            state_prefix = clause + " AND "
            success = conn.execute(
                "SELECT COUNT(*) AS n FROM tasks" + state_prefix + "state='SUCCESS'", params
            ).fetchone()["n"]
            failed = conn.execute(
                "SELECT COUNT(*) AS n FROM tasks" + state_prefix + "state='FAILED'", params
            ).fetchone()["n"]
            if tenant_id is None:
                failures = conn.execute(
                    "SELECT COUNT(*) AS n FROM failure_cases WHERE resolved=0"
                ).fetchone()["n"]
            else:
                failures = conn.execute(
                    "SELECT COUNT(*) AS n FROM failure_cases f JOIN tasks t ON t.id=f.task_id "
                    "WHERE f.resolved=0 AND t.tenant_id=?", (tenant_id,)
                ).fetchone()["n"]
            active_skills = conn.execute(
                "SELECT COUNT(*) AS n FROM skill_versions WHERE active = 1"
            ).fetchone()["n"]
            if tenant_id is None:
                active_skills += conn.execute(
                    "SELECT COUNT(*) AS n FROM skill_artifact_versions WHERE active=1"
                ).fetchone()["n"]
            else:
                active_skills += conn.execute(
                    "SELECT COUNT(*) AS n FROM skill_artifact_versions "
                    "WHERE tenant_id=? AND active=1", (tenant_id,)
                ).fetchone()["n"]
        return {
            "tasks_total": total, "tasks_success": success, "tasks_failed": failed,
            "success_rate": round(success / total, 4) if total else 0.0,
            "unresolved_failure_cases": failures, "active_skill_versions": active_skills,
        }
