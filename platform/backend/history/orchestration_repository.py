from __future__ import annotations

import builtins
import json
from datetime import datetime, timezone
from typing import Any

from agents.orchestration.schemas import (
    OrchestrationRunResponse,
)
from history.database import (
    HistoryDatabase,
    history_database,
)
from history.orchestration_schemas import (
    OrchestrationRunRecord,
    OrchestrationRunSummary,
    OrchestrationTaskRunRecord,
)


class OrchestrationRunRepository:
    def __init__(
        self,
        database: HistoryDatabase,
    ) -> None:
        self.database = database
        self.database.initialize()

    def save(
        self,
        response: OrchestrationRunResponse,
    ) -> OrchestrationRunRecord:
        now = datetime.now(
            timezone.utc,
        ).isoformat()

        plan_json = json.dumps(
            response.plan.model_dump(
                mode="json",
            ),
            ensure_ascii=False,
        )

        synthesis_json = (
            json.dumps(
                response.synthesis.model_dump(
                    mode="json",
                ),
                ensure_ascii=False,
            )
            if response.synthesis is not None
            else None
        )

        validation = (
            response.synthesis.validation if response.synthesis is not None else None
        )

        validation_json = (
            json.dumps(
                validation.model_dump(
                    mode="json",
                ),
                ensure_ascii=False,
            )
            if validation is not None
            else None
        )

        selected_agent_ids_json = json.dumps(
            response.plan.selected_agent_ids,
            ensure_ascii=False,
        )

        usage_json = json.dumps(
            response.usage.model_dump(
                mode="json",
            ),
            ensure_ascii=False,
        )

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO orchestration_runs (
                    run_id,
                    plan_id,
                    objective,
                    status,
                    execution_mode,
                    lead_agent_id,
                    selected_agent_ids_json,
                    plan_json,
                    synthesis_json,
                    validation_json,
                    final_answer,
                    usage_json,
                    error,
                    started_at,
                    completed_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(run_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    objective = excluded.objective,
                    status = excluded.status,
                    execution_mode = excluded.execution_mode,
                    lead_agent_id = excluded.lead_agent_id,
                    selected_agent_ids_json =
                        excluded.selected_agent_ids_json,
                    plan_json = excluded.plan_json,
                    synthesis_json = excluded.synthesis_json,
                    validation_json = excluded.validation_json,
                    final_answer = excluded.final_answer,
                    usage_json = excluded.usage_json,
                    error = excluded.error,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    response.orchestration_run_id,
                    response.plan.plan_id,
                    response.objective,
                    response.status,
                    response.plan.execution_mode,
                    response.plan.lead_agent_id,
                    selected_agent_ids_json,
                    plan_json,
                    synthesis_json,
                    validation_json,
                    response.final_answer,
                    usage_json,
                    response.error,
                    response.started_at.isoformat(),
                    response.completed_at.isoformat(),
                    now,
                    now,
                ),
            )

            connection.execute(
                """
                DELETE FROM orchestration_task_runs
                WHERE orchestration_run_id = ?
                """,
                (response.orchestration_run_id,),
            )

            tasks_by_id = {task.task_id: task for task in response.plan.tasks}

            for result in response.task_results:
                planned_task = tasks_by_id.get(
                    result.task_id,
                )

                depends_on = planned_task.depends_on if planned_task is not None else []

                connection.execute(
                    """
                    INSERT INTO orchestration_task_runs (
                        orchestration_run_id,
                        task_id,
                        sequence,
                        agent_id,
                        agent_name,
                        role,
                        status,
                        depends_on_json,
                        answer,
                        steps_json,
                        sources_json,
                        usage_json,
                        error,
                        started_at,
                        completed_at,
                        created_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        response.orchestration_run_id,
                        result.task_id,
                        result.sequence,
                        result.agent_id,
                        result.agent_name,
                        result.role,
                        result.status,
                        json.dumps(
                            depends_on,
                            ensure_ascii=False,
                        ),
                        result.answer,
                        json.dumps(
                            [
                                step.model_dump(
                                    mode="json",
                                )
                                for step in result.steps
                            ],
                            ensure_ascii=False,
                            default=str,
                        ),
                        json.dumps(
                            result.sources,
                            ensure_ascii=False,
                            default=str,
                        ),
                        json.dumps(
                            result.usage.model_dump(
                                mode="json",
                            ),
                            ensure_ascii=False,
                        ),
                        result.error,
                        result.started_at.isoformat(),
                        result.completed_at.isoformat(),
                        now,
                    ),
                )

            connection.commit()

        record = self.get(
            response.orchestration_run_id,
        )

        if record is None:
            raise RuntimeError("Saved orchestration run could not be read.")

        return record

    def get(
        self,
        run_id: str,
    ) -> OrchestrationRunRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM orchestration_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

            if row is None:
                return None

            task_rows = connection.execute(
                """
                SELECT *
                FROM orchestration_task_runs
                WHERE orchestration_run_id = ?
                ORDER BY sequence ASC, id ASC
                """,
                (run_id,),
            ).fetchall()

        task_runs = [
            self._row_to_task_record(
                task_row,
            )
            for task_row in task_rows
        ]

        return self._row_to_record(
            row,
            task_runs,
        )

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        execution_mode: str | None = None,
        lead_agent_id: str | None = None,
        validation_status: str | None = None,
        search: str | None = None,
    ) -> tuple[
        builtins.list[OrchestrationRunSummary],
        int,
    ]:
        conditions: builtins.list[str] = []
        parameters: builtins.list[Any] = []

        if status:
            conditions.append(
                "orchestration_runs.status = ?",
            )
            parameters.append(
                status,
            )

        if execution_mode:
            conditions.append(
                """
                orchestration_runs.execution_mode = ?
                """,
            )
            parameters.append(
                execution_mode,
            )

        if lead_agent_id:
            conditions.append(
                """
                orchestration_runs.lead_agent_id = ?
                """,
            )
            parameters.append(
                lead_agent_id,
            )

        if validation_status:
            conditions.append(
                """
                json_extract(
                    orchestration_runs.validation_json,
                    '$.status'
                ) = ?
                """,
            )
            parameters.append(
                validation_status,
            )

        if search:
            conditions.append(
                """
                (
                    orchestration_runs.objective LIKE ?
                    OR orchestration_runs.final_answer LIKE ?
                    OR orchestration_runs.lead_agent_id LIKE ?
                    OR orchestration_runs.run_id LIKE ?
                )
                """,
            )

            search_value = f"%{search}%"

            parameters.extend(
                [
                    search_value,
                    search_value,
                    search_value,
                    search_value,
                ],
            )

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(
                conditions,
            )

        with self.database.connection() as connection:
            total_row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM orchestration_runs
                {where_clause}
                """,
                parameters,
            ).fetchone()

            rows = connection.execute(
                f"""
                SELECT
                    orchestration_runs.*,
                    COUNT(
                        orchestration_task_runs.id
                    ) AS task_count,
                    SUM(
                        CASE
                            WHEN orchestration_task_runs.status
                                = 'completed'
                            THEN 1
                            ELSE 0
                        END
                    ) AS completed_task_count,
                    SUM(
                        CASE
                            WHEN orchestration_task_runs.status
                                = 'failed'
                            THEN 1
                            ELSE 0
                        END
                    ) AS failed_task_count
                FROM orchestration_runs
                LEFT JOIN orchestration_task_runs
                    ON orchestration_task_runs
                        .orchestration_run_id
                    = orchestration_runs.run_id
                {where_clause}
                GROUP BY orchestration_runs.run_id
                ORDER BY orchestration_runs.started_at DESC
                LIMIT ? OFFSET ?
                """,
                [
                    *parameters,
                    limit,
                    offset,
                ],
            ).fetchall()

        total = int(total_row["total"] if total_row is not None else 0)

        return (
            [
                self._row_to_summary(
                    row,
                )
                for row in rows
            ],
            total,
        )

    def delete(
        self,
        run_id: str,
    ) -> bool:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM orchestration_runs
                WHERE run_id = ?
                """,
                (run_id,),
            )

            connection.commit()

        return cursor.rowcount > 0

    def clear(self) -> int:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM orchestration_runs
                """
            )

            connection.commit()

        return max(
            cursor.rowcount,
            0,
        )

    @staticmethod
    def _load_json(
        value: str | None,
        default: Any,
    ) -> Any:
        if not value:
            return default

        try:
            return json.loads(
                value,
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            return default

    def _row_to_record(
        self,
        row: Any,
        task_runs: builtins.list[OrchestrationTaskRunRecord],
    ) -> OrchestrationRunRecord:
        synthesis = self._load_json(
            row["synthesis_json"],
            None,
        )

        validation = self._load_json(
            row["validation_json"],
            None,
        )

        return OrchestrationRunRecord(
            run_id=row["run_id"],
            plan_id=row["plan_id"],
            objective=row["objective"],
            status=row["status"],
            execution_mode=(row["execution_mode"]),
            lead_agent_id=(row["lead_agent_id"]),
            selected_agent_ids=(
                self._load_json(
                    row["selected_agent_ids_json"],
                    [],
                )
            ),
            plan=self._load_json(
                row["plan_json"],
                {},
            ),
            synthesis=synthesis,
            validation=validation,
            final_answer=(row["final_answer"] or ""),
            usage=self._load_json(
                row["usage_json"],
                {},
            ),
            error=row["error"],
            task_runs=task_runs,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_summary(
        self,
        row: Any,
    ) -> OrchestrationRunSummary:
        final_answer = row["final_answer"] or ""

        final_answer_preview = final_answer[:240] + (
            "…" if len(final_answer) > 240 else ""
        )

        usage = self._load_json(
            row["usage_json"],
            {},
        )

        validation = self._load_json(
            row["validation_json"],
            {},
        )

        return OrchestrationRunSummary(
            run_id=row["run_id"],
            plan_id=row["plan_id"],
            objective=row["objective"],
            status=row["status"],
            execution_mode=(row["execution_mode"]),
            lead_agent_id=(row["lead_agent_id"]),
            selected_agent_ids=(
                self._load_json(
                    row["selected_agent_ids_json"],
                    [],
                )
            ),
            task_count=int(
                row["task_count"] or 0,
            ),
            completed_task_count=int(
                row["completed_task_count"] or 0,
            ),
            failed_task_count=int(
                row["failed_task_count"] or 0,
            ),
            final_answer_preview=(final_answer_preview),
            validation_status=(
                validation.get(
                    "status",
                )
                if isinstance(
                    validation,
                    dict,
                )
                else None
            ),
            validation_passed=(
                validation.get(
                    "passed",
                )
                if isinstance(
                    validation,
                    dict,
                )
                else None
            ),
            total_tokens=(
                usage.get(
                    "total_tokens",
                )
                if isinstance(
                    usage,
                    dict,
                )
                else None
            ),
            latency_ms=float(
                usage.get(
                    "latency_ms",
                    0.0,
                )
                if isinstance(
                    usage,
                    dict,
                )
                else 0.0
            ),
            error=row["error"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
        )

    def _row_to_task_record(
        self,
        row: Any,
    ) -> OrchestrationTaskRunRecord:
        return OrchestrationTaskRunRecord(
            id=row["id"],
            orchestration_run_id=(row["orchestration_run_id"]),
            task_id=row["task_id"],
            sequence=row["sequence"],
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            role=row["role"],
            status=row["status"],
            depends_on=self._load_json(
                row["depends_on_json"],
                [],
            ),
            answer=row["answer"] or "",
            steps=self._load_json(
                row["steps_json"],
                [],
            ),
            sources=self._load_json(
                row["sources_json"],
                [],
            ),
            usage=self._load_json(
                row["usage_json"],
                {},
            ),
            error=row["error"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
        )


orchestration_run_repository = OrchestrationRunRepository(
    history_database,
)
