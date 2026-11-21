"""Read projections and small review records shared by the two SQL stores."""

import json


class WorkbenchStore:
    workbench_postgres = False

    def init_workbench(self):
        with self._connect() as conn:
            for statement in (
                "CREATE INDEX IF NOT EXISTS idx_workbench_tasks ON tasks(tenant_id,created_at,id)",
                "CREATE INDEX IF NOT EXISTS idx_workbench_pr_tasks ON tasks(tenant_id,repository,pull_request,created_at)",
                "CREATE INDEX IF NOT EXISTS idx_workbench_release_events ON audit_log(tenant_id,action,resource)",
                "CREATE TABLE IF NOT EXISTS finding_dispositions (tenant_id TEXT NOT NULL, scope TEXT NOT NULL, "
                "finding_key TEXT NOT NULL, state TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, PRIMARY KEY(tenant_id,scope,finding_key))",
                "CREATE TABLE IF NOT EXISTS review_repository_settings (tenant_id TEXT NOT NULL, repository TEXT NOT NULL, "
                "publication TEXT NOT NULL, PRIMARY KEY(tenant_id,repository))",
            ):
                conn.execute(statement)

    def _wb_sql(self, query):
        return query.replace("?", "%s") if self.workbench_postgres else query

    def _wb_text(self, column, key):
        if self.workbench_postgres:
            return f"({column}->>'{key}')"
        return f"json_extract({column}, '$.{key}')"

    @staticmethod
    def _wb_row(row):
        values = dict(row)
        for key in ("input_json", "state_json", "detail_json"):
            if key in values and isinstance(values[key], str):
                values[key] = json.loads(values[key])
        for key in ("created_at", "updated_at"):
            if hasattr(values.get(key), "isoformat"):
                values[key] = values[key].isoformat()
        return values

    def _wb_select(self, query, params):
        with self._connect() as conn:
            return [self._wb_row(row) for row in conn.execute(self._wb_sql(query), tuple(params)).fetchall()]

    def workbench_tasks(self, tenant_id, repository, pull_request, state, limit, offset):
        job_type = self._wb_text("t.input_json", "job_type")
        conditions = ["t.tenant_id=?", f"{job_type} IS NULL", """(
            NOT EXISTS(SELECT 1 FROM repository_grants g WHERE g.tenant_id=t.tenant_id)
            OR EXISTS(SELECT 1 FROM repository_grants g WHERE g.tenant_id=t.tenant_id AND g.repository=t.repository)
        )"""]
        args = [tenant_id]
        for column, value in (("repository", repository), ("pull_request", pull_request), ("state", state)):
            if value not in (None, ""):
                conditions.append(f"t.{column}=?")
                args.append(value)
        return self._wb_select(
            "SELECT t.id,t.repository,t.pull_request,t.state,t.created_at,t.updated_at FROM tasks t WHERE "
            + " AND ".join(conditions) + " ORDER BY t.created_at DESC,t.id DESC LIMIT ? OFFSET ?",
            [*args, limit + 1, offset],
        )

    def task_header(self, task_id, tenant_id):
        rows = self._wb_select(
            "SELECT id,tenant_id,repository,pull_request,state,updated_at,created_at,input_json,error,"
            "cancel_requested,report_json IS NOT NULL AS has_report FROM tasks WHERE id=? AND tenant_id=?",
            [task_id, tenant_id],
        )
        if not rows:
            return None
        row = rows[0]
        row["input"] = row.pop("input_json")
        return row

    def pr_tasks(self, tenant_id, repository, pull_request, limit=12):
        head = self._wb_text("input_json", "head_sha")
        base = self._wb_text("input_json", "base_sha")
        updated = self._wb_text("input_json", "pr_updated_at")
        return self._wb_select(
            f"SELECT id,state,{head} AS head_sha,{base} AS base_sha,created_at FROM tasks "
            f"WHERE tenant_id=? AND repository=? AND pull_request=? AND {head} IS NOT NULL "
            f"ORDER BY COALESCE({updated}, '') DESC,created_at DESC,id DESC LIMIT ?",
            [tenant_id, repository, pull_request, limit],
        )

    def pr_snapshot_task(self, tenant_id, repository, pull_request, head_sha, base_sha):
        head, base = [self._wb_text("input_json", key) for key in ("head_sha", "base_sha")]
        rows = self._wb_select(
            "SELECT id,state FROM tasks WHERE tenant_id=? AND repository=? AND pull_request=? "
            f"AND {head}=? AND {base}=? ORDER BY created_at DESC,id DESC LIMIT 1",
            [tenant_id, repository, pull_request, head_sha, base_sha],
        )
        return rows[0] if rows else None

    def workbench_checkpoints(self, task_id, names):
        placeholders = ",".join("?" for _ in names)
        return {row["node"]: row["state_json"] for row in self._wb_select(
            f"SELECT node,state_json FROM checkpoints WHERE task_id=? AND node IN ({placeholders})",
            [task_id, *names],
        )}

    def task_coverage_counts(self, task_id):
        total = ("jsonb_array_length(state_json->'batches')" if self.workbench_postgres
                 else "json_array_length(state_json, '$.batches')")
        row = self._wb_select(
            f"SELECT MAX(CASE WHEN node='review-v2-plan' THEN {total} END) AS total,"
            "SUM(CASE WHEN node LIKE ? AND status='completed' THEN 1 ELSE 0 END) AS completed "
            "FROM checkpoints WHERE task_id=? AND (node='review-v2-plan' OR node LIKE ?)",
            ["review-v2-result-%", task_id, "review-v2-result-%"],
        )[0]
        return row["total"], row["completed"] or 0

    def task_batch_phase(self, task_id, batch_id):
        expression = ("state_json->'session'->>'phase'" if self.workbench_postgres
                      else "json_extract(state_json, '$.session.phase')")
        rows = self._wb_select(f"SELECT {expression} AS phase FROM checkpoints WHERE task_id=? AND node=?",
                               [task_id, f"review-v2-batch-{batch_id}:agentic-lead-session"])
        return rows[0]["phase"] if rows else None

    def evolution_jobs(self, tenant_id, kind, name, limit=30):
        kind_expr, name_expr, job_expr = [self._wb_text("t.input_json", key) for key in ("kind", "name", "job_type")]
        result = self._wb_text("c.state_json", "decision")
        version = ("c.state_json->'version'->>'version'" if self.workbench_postgres
                   else "json_extract(c.state_json, '$.version.version')")
        return self._wb_select(
            f"SELECT t.id,t.state,t.error,t.created_at,t.updated_at,{result} AS decision,{version} AS version "
            "FROM tasks t LEFT JOIN checkpoints c ON c.task_id=t.id AND c.node='evolution-result' "
            f"WHERE t.tenant_id=? AND {job_expr}='evolution' AND {kind_expr}=? AND {name_expr}=? "
            "ORDER BY t.created_at DESC,t.id DESC LIMIT ?", [tenant_id, kind, name, limit],
        )

    def evaluation_model_for_version(self, tenant_id, kind, name, number):
        kind_expr, name_expr = [self._wb_text("t.input_json", key) for key in ("kind", "name")]
        model = ("t.input_json->'evaluation_model'" if self.workbench_postgres
                 else "json_extract(t.input_json, '$.evaluation_model')")
        version = ("c.state_json->'version'->>'version'" if self.workbench_postgres
                   else "CAST(json_extract(c.state_json, '$.version.version') AS TEXT)")
        rows = self._wb_select(
            f"SELECT {model} AS detail_json FROM tasks t JOIN checkpoints c ON c.task_id=t.id AND c.node='evolution-result' "
            f"WHERE t.tenant_id=? AND {kind_expr}=? AND {name_expr}=? AND {version}=? ORDER BY t.created_at DESC LIMIT 1",
            [tenant_id, kind, name, str(number)],
        )
        return rows[0]["detail_json"] if rows else None

    def stable_release_history(self, tenant_id, kind, name):
        rows = self._wb_select(
            "SELECT detail_json FROM audit_log WHERE tenant_id=? AND action=? AND resource=?",
            [tenant_id, f"{kind}.publish", name],
        )
        return {version for row in rows if row["detail_json"].get("decision") == "activated"
                for version in (row["detail_json"].get("version"), row["detail_json"].get("previous_version"))
                if version is not None}

    def workbench_feedback(self, tenant_id, ids):
        from itertools import islice

        scoped = list(islice(dict.fromkeys(ids), 100))
        if not scoped:
            return []
        placeholders = ",".join("?" for _ in scoped)
        note = self._wb_text("f.payload_json", "note")
        return self._wb_select(
            f"SELECT f.id,f.task_id,f.category,f.resolved,{note} AS note FROM failure_cases f "
            f"JOIN tasks t ON t.id=f.task_id WHERE t.tenant_id=? AND f.id IN ({placeholders})",
            [tenant_id, *scoped],
        )

    def finding_dispositions(self, tenant_id, scopes):
        placeholders = ",".join("?" for _ in scopes)
        return {(row["scope"], row["finding_key"]): row for row in self._wb_select(
            "SELECT scope,finding_key,state,actor,note,updated_at FROM finding_dispositions "
            f"WHERE tenant_id=? AND scope IN ({placeholders})", [tenant_id, *scopes],
        )}

    def save_finding_disposition(self, tenant_id, scope, key, state, actor, note, updated_at):
        with self._connect() as conn:
            conn.execute(self._wb_sql(
                "INSERT INTO finding_dispositions VALUES (?,?,?,?,?,?,?) ON CONFLICT(tenant_id,scope,finding_key) "
                "DO UPDATE SET state=excluded.state,actor=excluded.actor,note=excluded.note,updated_at=excluded.updated_at"
            ), (tenant_id, scope, key, state, actor, note, updated_at))

    def repository_publication(self, tenant_id, repository):
        rows = self._wb_select("SELECT publication FROM review_repository_settings WHERE tenant_id=? AND repository=?",
                               [tenant_id, repository])
        return rows[0]["publication"] if rows else None

    def has_repository_grant(self, tenant_id, repository):
        return bool(self._wb_select("SELECT 1 AS granted FROM repository_grants WHERE tenant_id=? AND repository=?",
                                    [tenant_id, repository]))

    def save_repository_publication(self, tenant_id, repository, publication):
        with self._connect() as conn:
            conn.execute(self._wb_sql(
                "INSERT INTO review_repository_settings VALUES (?,?,?) ON CONFLICT(tenant_id,repository) "
                "DO UPDATE SET publication=excluded.publication"
            ), (tenant_id, repository, publication))

    def release_unassigned_webhook(self, delivery_id, tenant_id):
        with self._connect() as conn:
            conn.execute(self._wb_sql("DELETE FROM webhook_deliveries WHERE delivery_id=? AND tenant_id=? AND task_id IS NULL"),
                         (delivery_id, tenant_id))
