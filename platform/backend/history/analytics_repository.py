import json
from typing import Any

from history.analytics_schemas import (
    AgentAnalyticsItem,
    AnalyticsOverview,
    RecentAnalyticsRun,
)
from history.database import (
    HistoryDatabase,
    history_database,
)


class AgentAnalyticsRepository:
    def __init__(
        self,
        database: HistoryDatabase,
    ) -> None:
        self.database = database
        self.database.initialize()

    def get_overview(
        self,
    ) -> AnalyticsOverview:
        with self.database.connection() as connection:
            totals_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_runs,
                    SUM(
                        CASE
                            WHEN status = 'completed'
                            THEN 1
                            ELSE 0
                        END
                    ) AS completed_runs,
                    SUM(
                        CASE
                            WHEN status = 'failed'
                            THEN 1
                            ELSE 0
                        END
                    ) AS failed_runs,
                    SUM(
                        CASE
                            WHEN status = 'running'
                            THEN 1
                            ELSE 0
                        END
                    ) AS running_runs,
                    SUM(
                        CASE
                            WHEN status = 'cancelled'
                            THEN 1
                            ELSE 0
                        END
                    ) AS cancelled_runs,
                    SUM(
                        CASE
                            WHEN substr(started_at, 1, 10)
                                 = date('now')
                            THEN 1
                            ELSE 0
                        END
                    ) AS runs_today
                FROM agent_runs
                """
            ).fetchone()

            most_used_row = connection.execute(
                """
                SELECT
                    agent_id,
                    COUNT(*) AS run_count
                FROM agent_runs
                GROUP BY agent_id
                ORDER BY
                    run_count DESC,
                    agent_id ASC
                LIMIT 1
                """
            ).fetchone()

            usage_rows = connection.execute(
                """
                SELECT usage_json
                FROM agent_runs
                """
            ).fetchall()

        total_runs = self._as_int(
            totals_row["total_runs"]
            if totals_row
            else 0
        )

        completed_runs = self._as_int(
            totals_row["completed_runs"]
            if totals_row
            else 0
        )

        success_rate = self._percentage(
            completed_runs,
            total_runs,
        )

        total_tokens = 0
        latency_total = 0.0
        latency_count = 0

        for row in usage_rows:
            usage = self._load_usage(
                row["usage_json"]
            )

            total_tokens += self._as_int(
                usage.get("total_tokens")
            )

            latency = usage.get(
                "latency_ms"
            )

            if latency is not None:
                latency_total += self._as_float(
                    latency
                )
                latency_count += 1

        average_latency_ms = (
            latency_total / latency_count
            if latency_count
            else 0.0
        )

        return AnalyticsOverview(
            total_runs=total_runs,
            completed_runs=completed_runs,
            failed_runs=self._as_int(
                totals_row["failed_runs"]
                if totals_row
                else 0
            ),
            running_runs=self._as_int(
                totals_row["running_runs"]
                if totals_row
                else 0
            ),
            cancelled_runs=self._as_int(
                totals_row["cancelled_runs"]
                if totals_row
                else 0
            ),
            success_rate=success_rate,
            average_latency_ms=round(
                average_latency_ms,
                2,
            ),
            total_tokens=total_tokens,
            runs_today=self._as_int(
                totals_row["runs_today"]
                if totals_row
                else 0
            ),
            most_used_agent=(
                str(most_used_row["agent_id"])
                if most_used_row
                else None
            ),
        )

    def get_agents(
        self,
        *,
        limit: int = 100,
    ) -> list[AgentAnalyticsItem]:
        with self.database.connection() as connection:
            aggregate_rows = connection.execute(
                """
                SELECT
                    agent_id,
                    COUNT(*) AS runs,
                    SUM(
                        CASE
                            WHEN status = 'completed'
                            THEN 1
                            ELSE 0
                        END
                    ) AS completed_runs,
                    SUM(
                        CASE
                            WHEN status = 'failed'
                            THEN 1
                            ELSE 0
                        END
                    ) AS failed_runs,
                    MAX(started_at) AS last_used_at
                FROM agent_runs
                GROUP BY agent_id
                ORDER BY
                    runs DESC,
                    agent_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            usage_rows = connection.execute(
                """
                SELECT
                    agent_id,
                    usage_json
                FROM agent_runs
                """
            ).fetchall()

        usage_by_agent: dict[
            str,
            dict[str, float | int],
        ] = {}

        for row in usage_rows:
            agent_id = str(
                row["agent_id"]
            )

            usage = self._load_usage(
                row["usage_json"]
            )

            agent_usage = usage_by_agent.setdefault(
                agent_id,
                {
                    "total_tokens": 0,
                    "latency_total": 0.0,
                    "latency_count": 0,
                },
            )

            agent_usage["total_tokens"] = (
                self._as_int(
                    agent_usage["total_tokens"]
                )
                + self._as_int(
                    usage.get("total_tokens")
                )
            )

            latency = usage.get(
                "latency_ms"
            )

            if latency is not None:
                agent_usage["latency_total"] = (
                    self._as_float(
                        agent_usage["latency_total"]
                    )
                    + self._as_float(
                        latency
                    )
                )

                agent_usage["latency_count"] = (
                    self._as_int(
                        agent_usage["latency_count"]
                    )
                    + 1
                )

        agents: list[AgentAnalyticsItem] = []

        for row in aggregate_rows:
            agent_id = str(
                row["agent_id"]
            )

            runs = self._as_int(
                row["runs"]
            )

            completed_runs = self._as_int(
                row["completed_runs"]
            )

            agent_usage = usage_by_agent.get(
                agent_id,
                {},
            )

            latency_count = self._as_int(
                agent_usage.get(
                    "latency_count"
                )
            )

            latency_total = self._as_float(
                agent_usage.get(
                    "latency_total"
                )
            )

            average_latency_ms = (
                latency_total / latency_count
                if latency_count
                else 0.0
            )

            agents.append(
                AgentAnalyticsItem(
                    agent_id=agent_id,
                    runs=runs,
                    completed_runs=completed_runs,
                    failed_runs=self._as_int(
                        row["failed_runs"]
                    ),
                    success_rate=self._percentage(
                        completed_runs,
                        runs,
                    ),
                    average_latency_ms=round(
                        average_latency_ms,
                        2,
                    ),
                    total_tokens=self._as_int(
                        agent_usage.get(
                            "total_tokens"
                        )
                    ),
                    last_used_at=row[
                        "last_used_at"
                    ],
                )
            )

        return agents

    def get_recent(
        self,
        *,
        limit: int = 10,
    ) -> list[RecentAnalyticsRun]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    run_id,
                    agent_id,
                    objective,
                    model,
                    provider,
                    status,
                    usage_json,
                    started_at,
                    completed_at
                FROM agent_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        recent_runs: list[
            RecentAnalyticsRun
        ] = []

        for row in rows:
            usage = self._load_usage(
                row["usage_json"]
            )

            total_tokens_value = usage.get(
                "total_tokens"
            )

            recent_runs.append(
                RecentAnalyticsRun(
                    run_id=row["run_id"],
                    agent_id=row["agent_id"],
                    objective=row["objective"],
                    model=row["model"],
                    provider=row["provider"],
                    status=row["status"],
                    total_tokens=(
                        self._as_int(
                            total_tokens_value
                        )
                        if total_tokens_value
                        is not None
                        else None
                    ),
                    latency_ms=self._as_float(
                        usage.get(
                            "latency_ms"
                        )
                    ),
                    started_at=row[
                        "started_at"
                    ],
                    completed_at=row[
                        "completed_at"
                    ],
                )
            )

        return recent_runs

    @staticmethod
    def _load_usage(
        value: str | None,
    ) -> dict[str, Any]:
        if not value:
            return {}

        try:
            payload = json.loads(value)
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            return {}

        if not isinstance(payload, dict):
            return {}

        return payload

    @staticmethod
    def _as_int(
        value: Any,
    ) -> int:
        if value is None:
            return 0

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0

    @staticmethod
    def _as_float(
        value: Any,
    ) -> float:
        if value is None:
            return 0.0

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    @staticmethod
    def _percentage(
        numerator: int,
        denominator: int,
    ) -> float:
        if denominator <= 0:
            return 0.0

        return round(
            numerator / denominator * 100,
            2,
        )


agent_analytics_repository = (
    AgentAnalyticsRepository(
        history_database
    )
)
