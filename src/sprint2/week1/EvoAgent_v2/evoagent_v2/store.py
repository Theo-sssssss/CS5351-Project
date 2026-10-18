from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from typing import Optional

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
                    delivery_error TEXT NOT NULL DEFAULT ''
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
                """
            )

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

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

    def set_success(self, task_id: str, report: dict, metrics: dict) -> None:
        self._update(
            task_id,
            "UPDATE tasks SET state='SUCCESS',updated_at=?,error='',report_json=?,metrics_json=? WHERE id=?",
            (now(), json.dumps(report, ensure_ascii=False), json.dumps(metrics, ensure_ascii=False), task_id),
        )

    def set_failed(self, task_id: str, error: str) -> None:
        self._update(task_id, "UPDATE tasks SET state='FAILED',updated_at=?,error=? WHERE id=?", (now(), error[:1000], task_id))

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

    def recover_interrupted(self) -> int:
        with self.lock, self.connect() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET state='FAILED',updated_at=?,error='Service restarted before task completion' WHERE state IN ('PENDING','RUNNING')",
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
        return item
