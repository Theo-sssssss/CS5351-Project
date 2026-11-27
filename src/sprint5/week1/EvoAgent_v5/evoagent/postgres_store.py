# PostgreSQL 持久化后端：保存任务、轨迹、记忆、评测版本、租户授权及发布状态。
# 接口与 SQLite 存储对应；JSON 字段在数据库边界编码和还原。

"""PostgreSQL persistence backend.

The implementation mirrors TaskStore's public API and is selected when
EVOAGENT_DATABASE_URL starts with postgres. psycopg is an optional production
dependency so local development can remain zero-config.
"""
import hashlib
import json
from contextlib import contextmanager
from typing import Any, Dict, Optional

from .models import ReviewReport, TaskState, TraceEvent
from .store import utc_now
from .workbench_store import WorkbenchStore


# PostgreSQL 存储实现，与本地存储保持对应的业务接口。
class PostgresTaskStore(WorkbenchStore):
    workbench_postgres = True
    # 加载 PostgreSQL 驱动并保存连接参数，随后初始化表结构。
    def __init__(self, url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL mode requires: pip install psycopg[binary]") from exc
        self.psycopg = psycopg
        self.dict_row = dict_row
        self.url = url
        self._init()
        self.init_workbench()

    # 建立数据库连接，并设置本后端使用的行结果格式。
    def _connect(self):
        return self.psycopg.connect(self.url, row_factory=self.dict_row)

    # 创建所需表和索引，并执行已有数据库的兼容性初始化。
    def _init(self) -> None:
        statements = [
            """CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, repository TEXT NOT NULL,
                pull_request INTEGER, input_json JSONB NOT NULL, report_json JSONB,
                error TEXT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS trace_events (
                id BIGSERIAL PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), step INTEGER NOT NULL,
                state TEXT NOT NULL, message TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS failure_cases (
                id BIGSERIAL PRIMARY KEY, task_id TEXT NOT NULL,
                skill_name TEXT NOT NULL DEFAULT 'llm-review', category TEXT NOT NULL,
                payload_json JSONB NOT NULL, resolved BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS skill_versions (
                id BIGSERIAL PRIMARY KEY, skill_name TEXT NOT NULL, version INTEGER NOT NULL,
                prompt TEXT NOT NULL, score DOUBLE PRECISION NOT NULL, active BOOLEAN NOT NULL DEFAULT FALSE,
                parent_version INTEGER, created_at TIMESTAMPTZ NOT NULL, UNIQUE(skill_name, version))""",
            """CREATE TABLE IF NOT EXISTS installations (
                installation_id BIGINT PRIMARY KEY, account_login TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS evaluation_cases (
                id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, split TEXT NOT NULL,
                diff TEXT NOT NULL, expected_json JSONB NOT NULL, source TEXT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS evolution_runs (
                id TEXT PRIMARY KEY, skill_name TEXT NOT NULL, candidate_version INTEGER NOT NULL,
                baseline_version INTEGER, decision TEXT NOT NULL, candidate_score DOUBLE PRECISION NOT NULL,
                baseline_score DOUBLE PRECISION NOT NULL, metrics_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS skill_artifact_versions (
                id BIGSERIAL PRIMARY KEY, tenant_id TEXT NOT NULL DEFAULT 'default',
                skill_name TEXT NOT NULL, version INTEGER NOT NULL,
                artifact_json JSONB NOT NULL, artifact_sha256 TEXT NOT NULL,
                score DOUBLE PRECISION NOT NULL, active BOOLEAN NOT NULL DEFAULT FALSE,
                parent_version INTEGER, created_at TIMESTAMPTZ NOT NULL,
                UNIQUE(tenant_id, skill_name, version))""",
            """CREATE TABLE IF NOT EXISTS skill_evolution_runs (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL DEFAULT 'default',
                skill_name TEXT NOT NULL, candidate_version INTEGER NOT NULL,
                baseline_version INTEGER, decision TEXT NOT NULL,
                candidate_score DOUBLE PRECISION NOT NULL, baseline_score DOUBLE PRECISION NOT NULL,
                metrics_json JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL)""",
            "ALTER TABLE skill_artifact_versions ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default'",
            "ALTER TABLE skill_evolution_runs ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default'",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default'",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE installations ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default'",
            "ALTER TABLE failure_cases ADD COLUMN IF NOT EXISTS skill_name TEXT NOT NULL DEFAULT 'llm-review'",
            "CREATE INDEX IF NOT EXISTS idx_failure_cases_skill_unresolved ON failure_cases(skill_name,resolved,id)",
            """CREATE TABLE IF NOT EXISTS checkpoints (
                task_id TEXT NOT NULL REFERENCES tasks(id), node TEXT NOT NULL, status TEXT NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 1, state_json JSONB NOT NULL, error TEXT,
                updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(task_id,node))""",
            """CREATE TABLE IF NOT EXISTS task_payloads (
                task_id TEXT PRIMARY KEY REFERENCES tasks(id), diff TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS agent_messages (
                id BIGSERIAL PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
                sender TEXT NOT NULL, recipient TEXT NOT NULL, kind TEXT NOT NULL,
                correlation_id TEXT NOT NULL, content_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS webhook_deliveries (
                delivery_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, event_type TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL, task_id TEXT, received_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS memberships (
                user_id TEXT NOT NULL REFERENCES users(id), tenant_id TEXT NOT NULL, role TEXT NOT NULL,
                PRIMARY KEY(user_id,tenant_id))""",
            """CREATE TABLE IF NOT EXISTS repository_grants (
                tenant_id TEXT NOT NULL, repository TEXT NOT NULL, auto_fix BOOLEAN NOT NULL DEFAULT FALSE,
                PRIMARY KEY(tenant_id,repository))""",
            """CREATE TABLE IF NOT EXISTS audit_log (
                id BIGSERIAL PRIMARY KEY, tenant_id TEXT NOT NULL, actor TEXT NOT NULL,
                action TEXT NOT NULL, resource TEXT NOT NULL, detail_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS deployments (
                tenant_id TEXT NOT NULL, skill_name TEXT NOT NULL, stable_version INTEGER,
                candidate_version INTEGER, canary_percent INTEGER NOT NULL DEFAULT 0,
                shadow_percent INTEGER NOT NULL DEFAULT 0, max_error_rate DOUBLE PRECISION NOT NULL DEFAULT .1,
                min_samples INTEGER NOT NULL DEFAULT 20, status TEXT NOT NULL DEFAULT 'stable',
                samples INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(tenant_id,skill_name))""",
            """CREATE TABLE IF NOT EXISTS alerts (
                id BIGSERIAL PRIMARY KEY, tenant_id TEXT NOT NULL, alert_key TEXT NOT NULL,
                severity TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
                UNIQUE(tenant_id,alert_key,status))""",
            """CREATE TABLE IF NOT EXISTS agent_memories (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, repository TEXT NOT NULL,
                task_id TEXT NOT NULL DEFAULT '', agent TEXT NOT NULL DEFAULT '',
                scope TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL,
                keywords_json JSONB NOT NULL, metadata_json JSONB NOT NULL,
                importance DOUBLE PRECISION NOT NULL DEFAULT .5,
                created_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ)""",
            """CREATE INDEX IF NOT EXISTS idx_agent_memories_lookup
                ON agent_memories(tenant_id,repository,scope,created_at)""",
        ]
        with self._connect() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)

    # 创建初始任务记录，将输入元信息与租户绑定。
    def create(
        self, task_id: str, repository: str, pull_request: Optional[int],
        payload: Dict[str, Any], tenant_id: str = "default",
    ) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks(id,state,repository,pull_request,input_json,report_json,error,"
                "created_at,updated_at,tenant_id,cancel_requested) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,NULL,NULL,%s,%s,%s,FALSE)",
                (task_id, TaskState.PENDING.value, repository, pull_request,
                 json.dumps(payload), now, now, tenant_id),
            )

    # 同时更新任务状态与轨迹事件，保持进度记录可追溯。
    @contextmanager
    def review_lock(self, task_id):
        key = int.from_bytes(hashlib.sha256(task_id.encode()).digest()[:8], "big", signed=True)
        with self._connect() as conn:
            acquired = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (key,)).fetchone()
            conn.commit()
            yield acquired["acquired"]

    def transition(self, task_id: str, event: TraceEvent) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE tasks SET state=%s,updated_at=%s WHERE id=%s", (event.state.value, event.created_at, task_id))
            conn.execute(
                "INSERT INTO trace_events(task_id,step,state,message,created_at) VALUES (%s,%s,%s,%s,%s)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 将任务置为成功，保存最终报告并追加结束轨迹。
    def succeed(self, task_id: str, report: ReviewReport, event: TraceEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state=%s,report_json=%s::jsonb,updated_at=%s,error=NULL WHERE id=%s",
                (TaskState.SUCCESS.value, json.dumps(report.to_dict(), ensure_ascii=False), event.created_at, task_id),
            )
            conn.execute(
                "INSERT INTO trace_events(task_id,step,state,message,created_at) VALUES (%s,%s,%s,%s,%s)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 将任务置为失败，保存错误信息并追加失败轨迹。
    def fail(self, task_id: str, error: str, event: TraceEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state=%s,error=%s,updated_at=%s WHERE id=%s",
                (TaskState.FAILED.value, error[:2000], event.created_at, task_id),
            )
            conn.execute(
                "INSERT INTO trace_events(task_id,step,state,message,created_at) VALUES (%s,%s,%s,%s,%s)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 按任务标识及可选租户查询任务，解码输入、报告和附属执行记录。
    def get(self, task_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            query = "SELECT * FROM tasks WHERE id=%s"
            params = [task_id]
            if tenant_id is not None:
                query += " AND tenant_id=%s"
                params.append(tenant_id)
            row = conn.execute(query, params).fetchone()
            if not row:
                return None
            events = conn.execute(
                "SELECT step,state,message,created_at FROM trace_events WHERE task_id=%s ORDER BY id", (task_id,)
            ).fetchall()
            messages = conn.execute(
                "SELECT sender,recipient,kind,correlation_id,content_json,created_at "
                "FROM agent_messages WHERE task_id=%s ORDER BY id", (task_id,)
            ).fetchall()
        value = dict(row)
        value["input"] = value.pop("input_json")
        value["report"] = value.pop("report_json")
        value["trace"] = [dict(item) for item in events]
        value["collaboration"] = []
        for message in messages:
            item = dict(message)
            item["content"] = item.pop("content_json")
            item["created_at"] = item["created_at"].isoformat()
            value["collaboration"].append(item)
        for key in ("created_at", "updated_at"):
            value[key] = value[key].isoformat()
        for item in value["trace"]:
            item["created_at"] = item["created_at"].isoformat()
        return value

    # 追加一条角色间消息，记录发送方、接收方、消息类型和内容。
    def record_agent_message(self, task_id: str, message: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_messages(task_id,sender,recipient,kind,correlation_id,"
                "content_json,created_at) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (task_id, message["sender"], message["recipient"], message["kind"],
                 message.get("correlation_id", ""),
                 json.dumps(message.get("content", {}), ensure_ascii=False), utc_now()),
            )

    # 按记忆标识保存或更新内容及过期信息，返回规范化记录。
    def save_agent_memory(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "INSERT INTO agent_memories(id,tenant_id,repository,task_id,agent,scope,kind,"
                "content,keywords_json,metadata_json,importance,created_at,expires_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET "
                "importance=GREATEST(agent_memories.importance,EXCLUDED.importance),"
                "expires_at=EXCLUDED.expires_at RETURNING *",
                (
                    memory["id"], memory["tenant_id"], memory["repository"],
                    memory.get("task_id", ""), memory.get("agent", ""), memory["scope"],
                    memory["kind"], memory["content"],
                    json.dumps(memory.get("keywords", []), ensure_ascii=False),
                    json.dumps(memory.get("metadata", {}), ensure_ascii=False),
                    float(memory.get("importance", 0.5)), memory["created_at"],
                    memory.get("expires_at"),
                ),
            ).fetchone()
        return self._memory_from_row(row)

    # 在租户、仓库和作用域范围内查询记忆，并排除过期条目。
    def list_agent_memories(
        self, tenant_id: str, repository: str, scopes: tuple,
        limit: int = 100,
    ) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_memories WHERE tenant_id=%s AND repository=%s "
                "AND scope=ANY(%s) AND (expires_at IS NULL OR expires_at>%s) "
                "ORDER BY importance DESC,created_at DESC LIMIT %s",
                (
                    tenant_id, repository, list(scopes), utc_now(),
                    max(1, min(limit, 500)),
                ),
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    # 按提供的任务和作用域等条件删除记忆，返回删除数量。
    def delete_agent_memories(self, task_id: str = "", scope: str = "") -> int:
        clauses = []
        params = []
        if task_id:
            clauses.append("task_id=%s")
            params.append(task_id)
        if scope:
            clauses.append("scope=%s")
            params.append(scope)
        if not clauses:
            raise ValueError("memory deletion requires task_id or scope")
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_memories WHERE " + " AND ".join(clauses), params
            )
            return cursor.rowcount

    # 删除到期的记忆记录，避免过期观察参与后续召回。
    def purge_expired_agent_memories(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_memories WHERE expires_at IS NOT NULL AND expires_at<=%s",
                (utc_now(),),
            )
            return cursor.rowcount

    # 将数据库行中的 JSON 字段解码为记忆对象。
    @staticmethod
    def _memory_from_row(row) -> Dict[str, Any]:
        value = dict(row)
        value["keywords"] = value.pop("keywords_json")
        value["metadata"] = value.pop("metadata_json")
        for key in ("created_at", "expires_at"):
            if value.get(key) is not None:
                value[key] = value[key].isoformat()
        return value

    # 按可选租户读取最近任务，限制返回数量供列表展示。
    def list_tasks(self, limit: int = 50, tenant_id: Optional[str] = None) -> list:
        with self._connect() as conn:
            where = " WHERE NOT (input_json ? 'job_type')"
            if tenant_id is not None:
                where += " AND tenant_id=%s"
            params = ([tenant_id] if tenant_id is not None else []) + [max(1, min(limit, 200))]
            rows = conn.execute(
                "SELECT id,state,repository,pull_request,error,created_at,updated_at,tenant_id "
                "FROM tasks" + where + " ORDER BY created_at DESC LIMIT %s", params
            ).fetchall()
        values = [dict(row) for row in rows]
        for value in values:
            value["created_at"] = value["created_at"].isoformat()
            value["updated_at"] = value["updated_at"].isoformat()
        return values

    def interrupted_tasks(self):
        with self._connect() as conn:
            return [row["id"] for row in conn.execute(
                "SELECT id FROM tasks WHERE state IN ('PENDING','PLANNING','EXECUTING','REVIEWING') "
                "AND (input_json ? 'review_engine' OR input_json->>'job_type'='evolution') ORDER BY created_at"
            ).fetchall()]

    # 将审查反馈或执行错误保存为待处理案例，供后续演进消费。
    def record_failure_case(
        self, task_id: str, category: str, payload: Dict[str, Any],
        skill_name: str = "llm-review",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO failure_cases(task_id,skill_name,category,payload_json,created_at) "
                "VALUES (%s,%s,%s,%s::jsonb,%s)",
                (task_id, skill_name, category, json.dumps(payload, ensure_ascii=False), utc_now()),
            )

    # 按解决状态、租户和可选 Skill 查询反馈案例，避免跨租户或跨领域学习。
    def list_failure_cases(
        self, unresolved_only: bool = False, limit: int = 100,
        tenant_id: Optional[str] = None, skill_name: Optional[str] = None,
    ) -> list:
        joins = " f"
        clauses = []
        params = []
        if tenant_id is not None:
            joins += " JOIN tasks t ON t.id=f.task_id"
            clauses.append("t.tenant_id=%s")
            params.append(tenant_id)
        if unresolved_only:
            clauses.append("f.resolved=FALSE")
        if skill_name is not None:
            clauses.append("f.skill_name=%s")
            params.append(skill_name)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(max(1, min(limit, 500)))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT f.* FROM failure_cases" + joins + where
                + " ORDER BY f.id DESC LIMIT %s", params
            ).fetchall()
        values = [dict(row) for row in rows]
        for value in values:
            value["payload"] = value.pop("payload_json")
            value["created_at"] = value["created_at"].isoformat()
        return values

    # 读取指定任务在给定租户范围内的反馈，供任务详情展示。
    def list_task_failure_cases(
        self, task_id: str, tenant_id: Optional[str] = None,
    ) -> list:
        joins = " f"
        clauses = ["f.task_id=%s"]
        params = [task_id]
        if tenant_id is not None:
            joins += " JOIN tasks t ON t.id=f.task_id"
            clauses.append("t.tenant_id=%s")
            params.append(tenant_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT f.* FROM failure_cases" + joins
                + " WHERE " + " AND ".join(clauses)
                + " ORDER BY f.id DESC",
                params,
            ).fetchall()
        values = [dict(row) for row in rows]
        for value in values:
            value["payload"] = value.pop("payload_json")
            value["created_at"] = value["created_at"].isoformat()
        return values

    # 把已经用于成功演进的案例标记为已解决。
    def resolve_failure_cases(self, case_ids: list) -> None:
        ids = [int(value) for value in case_ids]
        if not ids:
            return
        with self._connect() as conn:
            conn.execute("UPDATE failure_cases SET resolved=TRUE WHERE id=ANY(%s)", (ids,))

    # 保存不可变评测案例；相同输入可幂等返回，冲突内容拒绝覆盖。
    def save_evaluation_case(
        self, name: str, split: str, diff: str, expected: list,
        source: str = "manual", active: bool = True,
    ) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "INSERT INTO evaluation_cases(name,split,diff,expected_json,source,active,created_at) "
                "VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s) ON CONFLICT(name) DO NOTHING RETURNING *",
                (name, split, diff, json.dumps(expected, ensure_ascii=False), source, active, utc_now()),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM evaluation_cases WHERE name=%s", (name,)
                ).fetchone()
                if (
                    row["split"] != split
                    or row["diff"] != diff
                    or row["expected_json"] != expected
                ):
                    raise ValueError(
                        "evaluation case names are immutable; use a new name for revised content"
                    )
        value = dict(row)
        value["expected"] = value.pop("expected_json")
        value["created_at"] = value["created_at"].isoformat()
        return value

    # 按数据划分和启用状态读取案例，限制单次回放规模。
    def list_evaluation_cases(
        self, split: Optional[str] = None, active_only: bool = True, limit: int = 100,
    ) -> list:
        clauses = []
        params = []
        if split:
            clauses.append("split=%s")
            params.append(split)
        if active_only:
            clauses.append("active=TRUE")
        query = "SELECT * FROM evaluation_cases"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id LIMIT %s"
        params.append(max(1, min(limit, 500)))
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        values = [dict(row) for row in rows]
        for value in values:
            value["expected"] = value.pop("expected_json")
            value["created_at"] = value["created_at"].isoformat()
        return values

    # 保存提示词候选的基线、分数、门禁决策和复现信息。
    def save_evolution_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO evolution_runs(id,skill_name,candidate_version,baseline_version,decision,"
                "candidate_score,baseline_score,metrics_json,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
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
                "SELECT * FROM evolution_runs ORDER BY created_at DESC LIMIT %s",
                (max(1, min(limit, 200)),),
            ).fetchall()
        values = [dict(row) for row in rows]
        for value in values:
            value["metrics"] = value.pop("metrics_json")
            value["created_at"] = value["created_at"].isoformat()
        return values

    # 更新已有演进记录的决策与指标，补充结构化候选信息。
    def update_evolution_run(self, run_id: str, decision: str, metrics: Dict[str, Any]) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE evolution_runs SET decision=%s,metrics_json=%s::jsonb WHERE id=%s",
                (decision, json.dumps(metrics, ensure_ascii=False), run_id),
            )
            return cursor.rowcount == 1

    # 查找指定 Skill 当前启用的提示词版本。
    def get_active_skill_version(self, skill_name: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM skill_versions WHERE skill_name=%s AND active=TRUE ORDER BY version DESC LIMIT 1",
                (skill_name,),
            ).fetchone()
        return dict(row) if row else None

    # 为提示词分配版本号并保存，必要时替换同 Skill 的活动版本。
    def save_skill_version(self, skill_name: str, prompt: str, score: float, activate: bool = False) -> Dict[str, Any]:
        active = self.get_active_skill_version(skill_name)
        with self._connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (skill_name,))
            row = conn.execute(
                "SELECT COALESCE(MAX(version),0) AS version FROM skill_versions WHERE skill_name=%s",
                (skill_name,),
            ).fetchone()
            version = int(row["version"]) + 1
            if activate:
                conn.execute("UPDATE skill_versions SET active=FALSE WHERE skill_name=%s", (skill_name,))
            conn.execute(
                "INSERT INTO skill_versions(skill_name,version,prompt,score,active,parent_version,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (skill_name, version, prompt, score, activate, active["version"] if active else None, utc_now()),
            )
        return {"skill_name": skill_name, "version": version, "score": score, "active": activate}

    # 列出指定 Skill 的提示词历史，供查看和回滚。
    def list_skill_versions(self, skill_name: str) -> list:
        with self._connect() as conn:
            return list(conn.execute("SELECT * FROM skill_versions WHERE skill_name=%s ORDER BY version DESC", (skill_name,)).fetchall())

    # 确认目标版本存在后切换活动标记，避免激活不存在的版本。
    def activate_skill_version(self, skill_name: str, version: int) -> bool:
        with self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM skill_versions WHERE skill_name=%s AND version=%s", (skill_name, version)).fetchone()
            if not exists:
                return False
            conn.execute("UPDATE skill_versions SET active=FALSE WHERE skill_name=%s", (skill_name,))
            conn.execute("UPDATE skill_versions SET active=TRUE WHERE skill_name=%s AND version=%s", (skill_name, version))
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
        active = self.get_active_skill_artifact(skill_name, tenant_id)
        with self._connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("artifact:" + skill_name,))
            row = conn.execute(
                "SELECT COALESCE(MAX(version),0) AS version FROM skill_artifact_versions "
                "WHERE tenant_id=%s AND skill_name=%s", (tenant_id, skill_name),
            ).fetchone()
            version = int(row["version"]) + 1
            if activate:
                conn.execute(
                    "UPDATE skill_artifact_versions SET active=FALSE WHERE tenant_id=%s AND skill_name=%s",
                    (tenant_id, skill_name),
                )
            created_at = utc_now()
            conn.execute(
                "INSERT INTO skill_artifact_versions(tenant_id,skill_name,version,artifact_json,"
                "artifact_sha256,score,active,parent_version,created_at) "
                "VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)",
                (tenant_id, skill_name, version, artifact_json, artifact_sha256, float(score), activate,
                 active["version"] if active else None, created_at),
            )
        return {
            "tenant_id": tenant_id, "skill_name": skill_name, "version": version, "score": float(score),
            "active": activate, "parent_version": active["version"] if active else None,
            "artifact_sha256": artifact_sha256, "created_at": created_at,
        }

    # 解码数据库中的 Skill 制品与附属元数据。
    @staticmethod
    def _decode_skill_artifact(row) -> Dict[str, Any]:
        value = dict(row)
        value["artifact"] = value.pop("artifact_json")
        value["active"] = bool(value["active"])
        if hasattr(value.get("created_at"), "isoformat"):
            value["created_at"] = value["created_at"].isoformat()
        return value

    # 读取指定租户、指定 Skill 的当前活动制品。
    def get_active_skill_artifact(
        self, skill_name: str, tenant_id: str = "default",
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM skill_artifact_versions WHERE tenant_id=%s AND skill_name=%s "
                "AND active=TRUE ORDER BY version DESC LIMIT 1", (tenant_id, skill_name),
            ).fetchone()
        return self._decode_skill_artifact(row) if row else None

    # 列出当前租户已激活的全部 Skill 制品，供覆盖磁盘版本。
    def list_active_skill_artifacts(self, tenant_id: str = "default") -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_artifact_versions WHERE tenant_id=%s AND active=TRUE "
                "ORDER BY skill_name", (tenant_id,)
            ).fetchall()
        return [self._decode_skill_artifact(row) for row in rows]

    # 读取某租户中指定 Skill 的版本历史。
    def list_skill_artifact_versions(
        self, skill_name: str, tenant_id: str = "default",
    ) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_artifact_versions WHERE tenant_id=%s AND skill_name=%s "
                "ORDER BY version DESC", (tenant_id, skill_name),
            ).fetchall()
        return [self._decode_skill_artifact(row) for row in rows]

    # 在租户范围内切换 Skill 活动制品，避免影响其他租户。
    def activate_skill_artifact(
        self, skill_name: str, version: int, tenant_id: str = "default",
    ) -> bool:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM skill_artifact_versions v WHERE v.tenant_id=%s "
                "AND v.skill_name=%s AND v.version=%s AND (v.active=TRUE OR EXISTS ("
                "SELECT 1 FROM skill_evolution_runs r WHERE r.tenant_id=v.tenant_id "
                "AND r.skill_name=v.skill_name AND r.candidate_version=v.version "
                "AND r.decision='activated'))",
                (tenant_id, skill_name, version),
            ).fetchone()
            if not exists:
                return False
            conn.execute(
                "UPDATE skill_artifact_versions SET active=FALSE WHERE tenant_id=%s AND skill_name=%s",
                (tenant_id, skill_name),
            )
            conn.execute(
                "UPDATE skill_artifact_versions SET active=TRUE WHERE tenant_id=%s AND skill_name=%s "
                "AND version=%s", (tenant_id, skill_name, version),
            )
        return True

    # 保存制品演进的候选版本、对比指标和最终决策。
    def save_skill_evolution_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO skill_evolution_runs(id,tenant_id,skill_name,candidate_version,baseline_version,"
                "decision,candidate_score,baseline_score,metrics_json,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
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
                    "SELECT * FROM skill_evolution_runs ORDER BY created_at DESC LIMIT %s",
                    (max(1, min(limit, 200)),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skill_evolution_runs WHERE tenant_id=%s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (tenant_id, max(1, min(limit, 200))),
                ).fetchall()
        values = [dict(row) for row in rows]
        for value in values:
            value["metrics"] = value.pop("metrics_json")
            value["created_at"] = value["created_at"].isoformat()
        return values

    # 独立保存原始 Diff，供异步执行和任务恢复读取。
    def save_task_payload(self, task_id: str, diff: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO task_payloads(task_id,diff,created_at) VALUES (%s,%s,%s) "
                "ON CONFLICT(task_id) DO UPDATE SET diff=EXCLUDED.diff,created_at=EXCLUDED.created_at",
                (task_id, diff, utc_now()),
            )

    # 合并任务输入元信息，保留未被本次更新覆盖的字段。
    def update_task_input(self, task_id: str, updates: Dict[str, Any]) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT input_json FROM tasks WHERE id=%s", (task_id,)
            ).fetchone()
            if not row:
                raise ValueError("task not found")
            value = dict(row["input_json"])
            value.update(updates)
            conn.execute(
                "UPDATE tasks SET input_json=%s::jsonb,updated_at=%s WHERE id=%s",
                (json.dumps(value, ensure_ascii=False), utc_now(), task_id),
            )

    # 读取原始 Diff；不存在时返回空值，由调用方决定是否重取或失败。
    def get_task_payload(self, task_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT diff FROM task_payloads WHERE task_id=%s", (task_id,)).fetchone()
        return row["diff"] if row else None

    # 按任务与节点写入输出、状态、尝试次数和错误，作为恢复依据。
    def save_checkpoint(
        self, task_id: str, node: str, state: Dict[str, Any], status: str = "completed",
        attempt: int = 1, error: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO checkpoints(task_id,node,status,attempt,state_json,error,updated_at) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s) ON CONFLICT(task_id,node) DO UPDATE SET "
                "status=EXCLUDED.status,attempt=EXCLUDED.attempt,state_json=EXCLUDED.state_json,"
                "error=EXCLUDED.error,updated_at=EXCLUDED.updated_at",
                (task_id, node, status, attempt, json.dumps(state, ensure_ascii=False),
                 error[:2000] or None, utc_now()),
            )

    # 读取任务的全部节点检查点，并还原保存的状态字典。
    def load_checkpoints(self, task_id: str) -> Dict[str, Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT node,status,attempt,state_json,error,updated_at FROM checkpoints "
                "WHERE task_id=%s ORDER BY updated_at", (task_id,)
            ).fetchall()
        result = {}
        for row in rows:
            item = dict(row)
            item["state"] = item.pop("state_json")
            item["updated_at"] = item["updated_at"].isoformat()
            result[item.pop("node")] = item
        return result

    # 为符合条件的任务设置取消请求，由运行时在节点边界响应。
    def request_cancel(self, task_id: str, tenant_id: Optional[str] = None) -> bool:
        query = "UPDATE tasks SET cancel_requested=TRUE,updated_at=%s WHERE id=%s AND state NOT IN ('SUCCESS','FAILED','CANCELLED')"
        params = [utc_now(), task_id]
        if tenant_id is not None:
            query += " AND tenant_id=%s"
            params.append(tenant_id)
        with self._connect() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0

    # 读取任务是否已请求取消或已经进入取消状态。
    def is_cancelled(self, task_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cancel_requested FROM tasks WHERE id=%s", (task_id,)
            ).fetchone()
        return bool(row and row["cancel_requested"])

    # 记录取消终态并追加轨迹，使任务详情反映取消结果。
    def cancel(self, task_id: str, event: TraceEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET state=%s,updated_at=%s WHERE id=%s",
                (TaskState.CANCELLED.value, event.created_at, task_id),
            )
            conn.execute(
                "INSERT INTO trace_events(task_id,step,state,message,created_at) "
                "VALUES (%s,%s,%s,%s,%s)",
                (task_id, event.step, event.state.value, event.message, event.created_at),
            )

    # 尝试占用 delivery ID 并绑定载荷指纹，识别重复事件及同 ID 内容冲突。
    def claim_webhook(
        self, delivery_id: str, tenant_id: str, event_type: str, payload_sha256: str,
    ) -> bool:
        if not delivery_id:
            raise ValueError("X-GitHub-Delivery is required")
        with self._connect() as conn:
            row = conn.execute(
                "INSERT INTO webhook_deliveries"
                "(delivery_id,tenant_id,event_type,payload_sha256,received_at) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT(delivery_id) DO NOTHING RETURNING delivery_id",
                (delivery_id, tenant_id, event_type, payload_sha256, utc_now()),
            ).fetchone()
            if row:
                return True
            existing = conn.execute(
                "SELECT payload_sha256 FROM webhook_deliveries WHERE delivery_id=%s",
                (delivery_id,),
            ).fetchone()
            if existing and existing["payload_sha256"] != payload_sha256:
                raise ValueError("delivery id was already used with a different payload")
            return False

    # 将已处理的 Webhook 关联到任务，供重复投递返回已有任务标识。
    def complete_webhook(self, delivery_id: str, task_id: Optional[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE webhook_deliveries SET task_id=%s WHERE delivery_id=%s",
                (task_id, delivery_id),
            )

    # 查询已接收事件记录，用于幂等响应和追踪任务。
    def get_webhook(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM webhook_deliveries WHERE delivery_id=%s", (delivery_id,)
            ).fetchone()
        return dict(row) if row else None

    # 创建用户及租户角色关系，已有同名用户保留原凭据。
    def create_user(
        self, user_id: str, username: str, password_hash: str,
        tenant_id: str, role: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(id,username,password_hash,created_at) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT(username) DO NOTHING",
                (user_id, username, password_hash, utc_now()),
            )
            row = conn.execute("SELECT id FROM users WHERE username=%s", (username,)).fetchone()
            conn.execute(
                "INSERT INTO memberships(user_id,tenant_id,role) VALUES (%s,%s,%s) "
                "ON CONFLICT(user_id,tenant_id) DO UPDATE SET role=EXCLUDED.role",
                (row["id"], tenant_id, role),
            )

    # 按用户名读取账号状态、密码摘要及租户成员关系。
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id,username,password_hash,active FROM users WHERE username=%s",
                (username,),
            ).fetchone()
            if not row:
                return None
            memberships = conn.execute(
                "SELECT tenant_id,role FROM memberships WHERE user_id=%s", (row["id"],)
            ).fetchall()
        value = dict(row)
        value["memberships"] = [dict(item) for item in memberships]
        return value

    # 保存租户对仓库的访问授权及是否允许自动修复。
    def grant_repository(self, tenant_id: str, repository: str, auto_fix: bool = False) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO repository_grants(tenant_id,repository,auto_fix) VALUES (%s,%s,%s) "
                "ON CONFLICT(tenant_id,repository) DO UPDATE SET auto_fix=EXCLUDED.auto_fix",
                (tenant_id, repository, auto_fix),
            )

    # 检查租户的仓库授权；修复场景额外检查自动修复开关。
    def repository_allowed(
        self, tenant_id: str, repository: str, require_auto_fix: bool = False,
    ) -> bool:
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM repository_grants WHERE tenant_id=%s", (tenant_id,)
            ).fetchone()["n"]
            row = conn.execute(
                "SELECT auto_fix FROM repository_grants WHERE tenant_id=%s AND repository=%s",
                (tenant_id, repository),
            ).fetchone()
        return True if total == 0 else bool(row and (not require_auto_fix or row["auto_fix"]))

    # 追加管理操作审计记录，保留操作者、动作和目标上下文。
    def audit(
        self, tenant_id: str, actor: str, action: str, resource: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log(tenant_id,actor,action,resource,detail_json,created_at) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,%s)",
                (tenant_id, actor, action, resource,
                 json.dumps(detail or {}, ensure_ascii=False), utc_now()),
            )

    # 按租户读取最近审计记录，供管理员或审计员查看。
    def list_audit(self, tenant_id: str, limit: int = 100) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT actor,action,resource,detail_json,created_at FROM audit_log "
                "WHERE tenant_id=%s ORDER BY id DESC LIMIT %s",
                (tenant_id, max(1, min(limit, 500))),
            ).fetchall()
        return [{**dict(row), "detail": row["detail_json"],
                 "created_at": row["created_at"].isoformat()} for row in rows]

    # 保存某租户的 Skill 灰度比例、影子模式与错误预算配置。
    def save_deployment(self, tenant_id: str, skill_name: str, config: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO deployments(tenant_id,skill_name,stable_version,candidate_version,"
                "canary_percent,shadow_percent,max_error_rate,min_samples,status,samples,errors,updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,%s) "
                "ON CONFLICT(tenant_id,skill_name) DO UPDATE SET stable_version=EXCLUDED.stable_version,"
                "candidate_version=EXCLUDED.candidate_version,canary_percent=EXCLUDED.canary_percent,"
                "shadow_percent=EXCLUDED.shadow_percent,max_error_rate=EXCLUDED.max_error_rate,"
                "min_samples=EXCLUDED.min_samples,status=EXCLUDED.status,samples=0,errors=0,"
                "updated_at=EXCLUDED.updated_at",
                (tenant_id, skill_name, config.get("stable_version"), config.get("candidate_version"),
                 int(config.get("canary_percent", 0)), int(config.get("shadow_percent", 0)),
                 float(config.get("max_error_rate", .1)), int(config.get("min_samples", 20)),
                 config.get("status", "running"), utc_now()),
            )

    # 查询租户当前的 Skill 发布状态与累计统计。
    def get_deployment(self, tenant_id: str, skill_name: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM deployments WHERE tenant_id=%s AND skill_name=%s",
                (tenant_id, skill_name),
            ).fetchone()
        return dict(row) if row else None

    # 累计指定发布分组的成功和失败，更新错误预算及回滚状态。
    def record_deployment_result(
        self, tenant_id: str, skill_name: str, failed: bool,
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "UPDATE deployments SET samples=samples+1,errors=errors+%s,updated_at=%s "
                "WHERE tenant_id=%s AND skill_name=%s RETURNING *",
                (int(failed), utc_now(), tenant_id, skill_name),
            ).fetchone()
            if not row:
                return None
            value = dict(row)
            if (value["status"] == "running" and value["samples"] >= value["min_samples"]
                    and value["errors"] / value["samples"] > value["max_error_rate"]):
                conn.execute(
                    "UPDATE deployments SET status='rolled_back',canary_percent=0,shadow_percent=0,"
                    "updated_at=%s WHERE tenant_id=%s AND skill_name=%s",
                    (utc_now(), tenant_id, skill_name),
                )
                value["status"] = "rolled_back"
        return value

    # 按告警键保存告警，记录级别、描述及时间。
    def create_alert(
        self, tenant_id: str, alert_key: str, severity: str, message: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO alerts(tenant_id,alert_key,severity,message,status,created_at,updated_at) "
                "VALUES (%s,%s,%s,%s,'open',%s,%s) ON CONFLICT(tenant_id,alert_key,status) DO NOTHING",
                (tenant_id, alert_key, severity, message[:1000], utc_now(), utc_now()),
            )

    # 读取租户范围内最近的持久化告警。
    def list_alerts(self, tenant_id: str, limit: int = 100) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE tenant_id=%s ORDER BY id DESC LIMIT %s",
                (tenant_id, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    # 保存 GitHub App 安装与租户之间的映射。
    def save_installation(
        self, installation_id: int, account_login: str, tenant_id: str = "default"
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO installations(installation_id,account_login,created_at,tenant_id) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT(installation_id) DO UPDATE "
                "SET account_login=EXCLUDED.account_login,created_at=EXCLUDED.created_at,"
                "tenant_id=EXCLUDED.tenant_id",
                (installation_id, account_login, utc_now(), tenant_id),
            )

    # 根据安装标识解析所属租户，供 Webhook 路由使用。
    def installation_tenant(self, installation_id: int) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tenant_id FROM installations WHERE installation_id=%s",
                (installation_id,),
            ).fetchone()
        return row["tenant_id"] if row else None

    # 汇总任务状态、近期结果及相关计数，供控制台与告警逻辑使用。
    def dashboard_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        with self._connect() as conn:
            where = " WHERE NOT (input_json ? 'job_type')"
            if tenant_id is not None:
                where += " AND tenant_id=%s"
            params = (tenant_id,) if tenant_id is not None else ()
            row = conn.execute(
                "SELECT COUNT(*) AS total,COUNT(*) FILTER(WHERE state='SUCCESS') AS success,"
                "COUNT(*) FILTER(WHERE state='FAILED') AS failed FROM tasks" + where,
                params,
            ).fetchone()
            if tenant_id is None:
                failures = conn.execute(
                    "SELECT COUNT(*) AS n FROM failure_cases WHERE resolved=FALSE"
                ).fetchone()["n"]
            else:
                failures = conn.execute(
                    "SELECT COUNT(*) AS n FROM failure_cases f JOIN tasks t ON t.id=f.task_id "
                    "WHERE f.resolved=FALSE AND t.tenant_id=%s", (tenant_id,)
                ).fetchone()["n"]
            skills = conn.execute(
                "SELECT COUNT(*) AS n FROM skill_versions WHERE active=TRUE"
            ).fetchone()["n"]
            if tenant_id is None:
                skills += conn.execute(
                    "SELECT COUNT(*) AS n FROM skill_artifact_versions WHERE active=TRUE"
                ).fetchone()["n"]
            else:
                skills += conn.execute(
                    "SELECT COUNT(*) AS n FROM skill_artifact_versions "
                    "WHERE tenant_id=%s AND active=TRUE", (tenant_id,)
                ).fetchone()["n"]
        return {"tasks_total": row["total"], "tasks_success": row["success"], "tasks_failed": row["failed"],
                "success_rate": round(row["success"] / row["total"], 4) if row["total"] else 0.0,
                "unresolved_failure_cases": failures, "active_skill_versions": skills}


# 根据数据库 URL 选择 PostgreSQL，否则使用本地 SQLite 文件。
def create_store(database_url: str, sqlite_path: str):
    if database_url.startswith(("postgres://", "postgresql://")):
        return PostgresTaskStore(database_url)
    from .store import TaskStore
    return TaskStore(sqlite_path)
