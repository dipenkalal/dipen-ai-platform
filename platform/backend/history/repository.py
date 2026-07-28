import json
from datetime import UTC, datetime
from typing import Any

from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
)

from history.database import (
    HistoryDatabase,
    history_database,
)
from history.schemas import (
    AgentRunRecord,
    AgentRunSummary,
)


class AgentRunRepository:
    def __init__(
        self,
        database: HistoryDatabase,
    ) -> None:
        self.database = database
        self.database.initialize()

    def save(
        self,
        request: AgentRunRequest,
        response: AgentRunResponse,
        error: str | None = None,
    ) -> AgentRunRecord:
        now = datetime.now(UTC).isoformat()

        request_json = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
        )

        steps_json = json.dumps(
            [step.model_dump(mode="json") for step in response.steps],
            ensure_ascii=False,
        )

        sources_json = json.dumps(
            response.sources,
            ensure_ascii=False,
            default=str,
        )

        usage_json = json.dumps(
            response.usage.model_dump(mode="json"),
            ensure_ascii=False,
        )

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs (
                    run_id,
                    agent_id,
                    objective,
                    model,
                    provider,
                    status,
                    answer,
                    error,
                    request_json,
                    steps_json,
                    sources_json,
                    usage_json,
                    started_at,
                    completed_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(run_id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    objective = excluded.objective,
                    model = excluded.model,
                    provider = excluded.provider,
                    status = excluded.status,
                    answer = excluded.answer,
                    error = excluded.error,
                    request_json = excluded.request_json,
                    steps_json = excluded.steps_json,
                    sources_json = excluded.sources_json,
                    usage_json = excluded.usage_json,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    response.run_id,
                    response.agent_id,
                    response.objective,
                    request.model,
                    request.provider,
                    response.status,
                    response.answer,
                    error,
                    request_json,
                    steps_json,
                    sources_json,
                    usage_json,
                    response.started_at.isoformat(),
                    response.completed_at.isoformat(),
                    now,
                    now,
                ),
            )

            connection.commit()

        record = self.get(response.run_id)

        if record is None:
            raise RuntimeError("Saved agent run could not be read.")

        return record

    def get(
        self,
        run_id: str,
    ) -> AgentRunRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM agent_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        agent_id: str | None = None,
        status: str | None = None,
        model: str | None = None,
        search: str | None = None,
    ) -> tuple[list[AgentRunSummary], int]:
        conditions: list[str] = []
        parameters: list[Any] = []

        if agent_id:
            conditions.append("agent_id = ?")
            parameters.append(agent_id)

        if status:
            conditions.append("status = ?")
            parameters.append(status)

        if model:
            conditions.append("model = ?")
            parameters.append(model)

        if search:
            conditions.append("""
                (
                    objective LIKE ?
                    OR answer LIKE ?
                    OR agent_id LIKE ?
                )
                """)

            search_value = f"%{search}%"

            parameters.extend(
                [
                    search_value,
                    search_value,
                    search_value,
                ]
            )

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        with self.database.connection() as connection:
            total_row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM agent_runs
                {where_clause}
                """,
                parameters,
            ).fetchone()

            rows = connection.execute(
                f"""
                SELECT *
                FROM agent_runs
                {where_clause}
                ORDER BY started_at DESC
                LIMIT ? OFFSET ?
                """,
                [
                    *parameters,
                    limit,
                    offset,
                ],
            ).fetchall()

        total = int(total_row["total"] if total_row else 0)

        return (
            [self._row_to_summary(row) for row in rows],
            total,
        )

    def delete(
        self,
        run_id: str,
    ) -> bool:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM agent_runs
                WHERE run_id = ?
                """,
                (run_id,),
            )

            connection.commit()

        return cursor.rowcount > 0

    def clear(self) -> int:
        with self.database.connection() as connection:
            cursor = connection.execute("DELETE FROM agent_runs")

            connection.commit()

        return max(
            cursor.rowcount,
            0,
        )

    def _row_to_record(
        self,
        row: Any,
    ) -> AgentRunRecord:
        usage = json.loads(row["usage_json"])

        return AgentRunRecord(
            run_id=row["run_id"],
            agent_id=row["agent_id"],
            objective=row["objective"],
            model=row["model"],
            provider=row["provider"],
            status=row["status"],
            answer=row["answer"],
            error=row["error"],
            request=json.loads(row["request_json"]),
            steps=json.loads(row["steps_json"]),
            sources=json.loads(row["sources_json"]),
            usage=usage,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_summary(
        self,
        row: Any,
    ) -> AgentRunSummary:
        usage = json.loads(row["usage_json"])

        steps = json.loads(row["steps_json"])

        sources = json.loads(row["sources_json"])

        answer = row["answer"] or ""

        answer_preview = answer[:240] + ("…" if len(answer) > 240 else "")

        return AgentRunSummary(
            run_id=row["run_id"],
            agent_id=row["agent_id"],
            objective=row["objective"],
            model=row["model"],
            provider=row["provider"],
            status=row["status"],
            answer_preview=answer_preview,
            error=row["error"],
            step_count=len(steps),
            source_count=len(sources),
            total_tokens=usage.get("total_tokens"),
            latency_ms=usage.get(
                "latency_ms",
                0.0,
            ),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
        )


agent_run_repository = AgentRunRepository(history_database)
