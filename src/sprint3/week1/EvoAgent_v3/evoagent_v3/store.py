from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from .models import now


class Store:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    repository TEXT NOT NULL,
                    pull_request INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    report_json TEXT,
                    metrics_json TEXT,
                    delivery_state TEXT NOT NULL DEFAULT 'NOT_REQUESTED',
                    delivery_error TEXT NOT NULL DEFAULT '',
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    diff_sha256 TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS role_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    phase INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    model TEXT NOT NULL DEFAULT '',
                    input_sha256 TEXT NOT NULL DEFAULT '',
                    output_json TEXT,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    task_id TEXT NOT NULL,
                    node TEXT NOT NULL,
                    state TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(task_id,node),
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                CREATE TABLE IF NOT EXISTS tool_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    tool TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                """
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def create_task(self, repository: str, number: int, source: str, mode: str) -> str:
        task_id = str(uuid.uuid4())
        timestamp = now()
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO tasks(id,repository,pull_request,source,mode,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (task_id, repository, number, source, mode, "PENDING", timestamp, timestamp),
            )
        return task_id

    def set_running(self, task_id: str) -> None:
        self._update(task_id, "UPDATE tasks SET state='RUNNING',updated_at=?,error='' WHERE id=?", (now(), task_id))

    def clear_cancel_request(self, task_id: str) -> None:
        self._update(task_id, "UPDATE tasks SET cancel_requested=0,updated_at=? WHERE id=?", (now(), task_id))

    def set_diff_fingerprint(self, task_id: str, digest: str) -> None:
        self._update(task_id, "UPDATE tasks SET diff_sha256=?,updated_at=? WHERE id=?", (digest, now(), task_id))

    def set_success(self, task_id: str, report: dict, metrics: dict) -> None:
        self._update(
            task_id,
            "UPDATE tasks SET state='SUCCESS',updated_at=?,error='',report_json=?,metrics_json=? WHERE id=?",
            (now(), json.dumps(report, ensure_ascii=False), json.dumps(metrics, ensure_ascii=False), task_id),
        )

    def set_failed(self, task_id: str, error: str) -> None:
        self._update(task_id, "UPDATE tasks SET state='FAILED',updated_at=?,error=? WHERE id=?", (now(), error[:1000], task_id))

    def set_cancelled(self, task_id: str, error: str = "Task cancellation requested") -> None:
        self._update(task_id, "UPDATE tasks SET state='CANCELLED',updated_at=?,error=? WHERE id=?", (now(), error[:1000], task_id))

    def request_cancel(self, task_id: str) -> bool:
        with self.lock, self.connect() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET cancel_requested=1,updated_at=? WHERE id=? AND state IN ('PENDING','RUNNING')",
                (now(), task_id),
            )
            return cursor.rowcount == 1

    def is_cancel_requested(self, task_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT cancel_requested FROM tasks WHERE id=?", (task_id,)).fetchone()
        return bool(row and row[0])

    def set_delivery(self, task_id: str, state: str, error: str = "") -> None:
        self._update(
            task_id,
            "UPDATE tasks SET delivery_state=?,delivery_error=?,updated_at=? WHERE id=?",
            (state, error[:1000], now(), task_id),
        )

    def _update(self, _task_id: str, sql: str, values: tuple) -> None:
        with self.lock, self.connect() as conn:
            conn.execute(sql, values)

    def start_role(self, task_id: str, role: str, phase: int, model: str, input_sha256: str) -> int:
        with self.lock, self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO role_runs(task_id,role,phase,state,started_at,model,input_sha256) VALUES (?,?,?,?,?,?,?)",
                (task_id, role, phase, "RUNNING", now(), model, input_sha256),
            )
            return int(cursor.lastrowid)

    def finish_role(self, run_id: int, output: dict, latency_ms: int, input_tokens: int, output_tokens: int) -> None:
        with self.lock, self.connect() as conn:
            conn.execute(
                "UPDATE role_runs SET state='SUCCESS',completed_at=?,latency_ms=?,output_json=?,input_tokens=?,output_tokens=? WHERE id=?",
                (now(), latency_ms, json.dumps(output, ensure_ascii=False), input_tokens, output_tokens, run_id),
            )

    def fail_role(self, run_id: int, error: str, latency_ms: int) -> None:
        with self.lock, self.connect() as conn:
            conn.execute(
                "UPDATE role_runs SET state='FAILED',completed_at=?,latency_ms=?,error=? WHERE id=?",
                (now(), latency_ms, error[:1000], run_id),
            )

    def get(self, task_id: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        task = self._task_row(row)
        task["role_runs"] = self.role_runs(task_id)
        task["tool_events"] = self.tool_events(task_id)
        task["checkpoints"] = self.checkpoints(task_id)
        return task

    def list_tasks(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100").fetchall()
        return [self._task_row(row) for row in rows]

    def role_runs(self, task_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM role_runs WHERE task_id=? ORDER BY phase,id", (task_id,)).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["output"] = json.loads(item.pop("output_json") or "null")
            values.append(item)
        return values

    def remember_delivery(self, delivery_id: str) -> bool:
        if not delivery_id:
            return True
        try:
            with self.lock, self.connect() as conn:
                conn.execute("INSERT INTO deliveries(delivery_id,created_at) VALUES (?,?)", (delivery_id, now()))
            return True
        except sqlite3.IntegrityError:
            return False

    def save_checkpoint(self, task_id: str, node: str, state: str, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        with self.lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints(task_id,node,state,data_json,updated_at) VALUES (?,?,?,?,?)
                ON CONFLICT(task_id,node) DO UPDATE SET state=excluded.state,data_json=excluded.data_json,updated_at=excluded.updated_at
                """,
                (task_id, node, state, payload, now()),
            )

    def get_checkpoint(self, task_id: str, node: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM checkpoints WHERE task_id=? AND node=?", (task_id, node)).fetchone()
        if not row:
            return None
        value = dict(row)
        value["data"] = json.loads(value.pop("data_json"))
        return value

    def checkpoints(self, task_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM checkpoints WHERE task_id=? ORDER BY updated_at,node", (task_id,)).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["data"] = json.loads(item.pop("data_json"))
            values.append(item)
        return values

    def record_tool_event(
        self,
        task_id: str,
        role: str,
        step: int,
        tool: str,
        arguments: dict,
        output: dict,
        state: str,
        latency_ms: int,
    ) -> None:
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO tool_events(task_id,role,step,tool,arguments_json,output_json,state,latency_ms,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    role,
                    step,
                    tool,
                    json.dumps(arguments, ensure_ascii=False),
                    json.dumps(output, ensure_ascii=False),
                    state,
                    latency_ms,
                    now(),
                ),
            )

    def tool_events(self, task_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tool_events WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
        values = []
        for row in rows:
            item = dict(row)
            item["arguments"] = json.loads(item.pop("arguments_json"))
            item["output"] = json.loads(item.pop("output_json"))
            values.append(item)
        return values

    def recover_interrupted(self) -> int:
        with self.lock, self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET state=CASE WHEN mode='agentic' THEN 'PAUSED' ELSE 'FAILED' END,
                    updated_at=?,
                    error=CASE WHEN mode='agentic' THEN 'Service restarted; resume from checkpoint' ELSE 'Service restarted before task completion' END
                WHERE state IN ('PENDING','RUNNING')
                """,
                (now(),),
            )
            conn.execute(
                "UPDATE role_runs SET state='FAILED',completed_at=?,error='Service restarted before role completion' WHERE state='RUNNING'",
                (now(),),
            )
            return int(cursor.rowcount)

    @staticmethod
    def _task_row(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["report"] = json.loads(item.pop("report_json") or "null")
        item["metrics"] = json.loads(item.pop("metrics_json") or "null")
        item["cancel_requested"] = bool(item["cancel_requested"])
        return item
