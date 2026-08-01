import json
from collections import Counter
from typing import Any

from history.analytics_schemas import (
    AgentAnalyticsItem,
    AnalyticsOverview,
    RecentAnalyticsRun,
    RoutingAnalytics,
    RoutingMatchedTerm,
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

        total_runs = self._as_int(totals_row["total_runs"] if totals_row else 0)

        completed_runs = self._as_int(totals_row["completed_runs"] if totals_row else 0)

        success_rate = self._percentage(
            completed_runs,
            total_runs,
        )

        total_tokens = 0
        latency_total = 0.0
        latency_count = 0

        for row in usage_rows:
            usage = self._load_usage(row["usage_json"])

            total_tokens += self._as_int(usage.get("total_tokens"))

            latency = usage.get("latency_ms")

            if latency is not None:
                latency_total += self._as_float(latency)
                latency_count += 1

        average_latency_ms = latency_total / latency_count if latency_count else 0.0

        return AnalyticsOverview(
            total_runs=total_runs,
            completed_runs=completed_runs,
            failed_runs=self._as_int(totals_row["failed_runs"] if totals_row else 0),
            running_runs=self._as_int(totals_row["running_runs"] if totals_row else 0),
            cancelled_runs=self._as_int(
                totals_row["cancelled_runs"] if totals_row else 0
            ),
            success_rate=success_rate,
            average_latency_ms=round(
                average_latency_ms,
                2,
            ),
            total_tokens=total_tokens,
            runs_today=self._as_int(totals_row["runs_today"] if totals_row else 0),
            most_used_agent=(str(most_used_row["agent_id"]) if most_used_row else None),
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
            agent_id = str(row["agent_id"])

            usage = self._load_usage(row["usage_json"])

            agent_usage = usage_by_agent.setdefault(
                agent_id,
                {
                    "total_tokens": 0,
                    "latency_total": 0.0,
                    "latency_count": 0,
                },
            )

            agent_usage["total_tokens"] = self._as_int(
                agent_usage["total_tokens"]
            ) + self._as_int(usage.get("total_tokens"))

            latency = usage.get("latency_ms")

            if latency is not None:
                agent_usage["latency_total"] = self._as_float(
                    agent_usage["latency_total"]
                ) + self._as_float(latency)

                agent_usage["latency_count"] = (
                    self._as_int(agent_usage["latency_count"]) + 1
                )

        agents: list[AgentAnalyticsItem] = []

        for row in aggregate_rows:
            agent_id = str(row["agent_id"])

            runs = self._as_int(row["runs"])

            completed_runs = self._as_int(row["completed_runs"])

            agent_usage = usage_by_agent.get(
                agent_id,
                {},
            )

            latency_count = self._as_int(agent_usage.get("latency_count"))

            latency_total = self._as_float(agent_usage.get("latency_total"))

            average_latency_ms = latency_total / latency_count if latency_count else 0.0

            agents.append(
                AgentAnalyticsItem(
                    agent_id=agent_id,
                    runs=runs,
                    completed_runs=completed_runs,
                    failed_runs=self._as_int(row["failed_runs"]),
                    success_rate=self._percentage(
                        completed_runs,
                        runs,
                    ),
                    average_latency_ms=round(
                        average_latency_ms,
                        2,
                    ),
                    total_tokens=self._as_int(agent_usage.get("total_tokens")),
                    last_used_at=row["last_used_at"],
                )
            )

        return agents

    def get_routing(
        self,
    ) -> RoutingAnalytics:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT request_json
                FROM agent_runs
                """
            ).fetchall()

        smart_runs = 0
        manual_runs = 0

        confidence_total = 0.0
        confidence_count = 0

        routing_latency_total = 0.0
        routing_latency_count = 0

        selected_agents: Counter[str] = Counter()
        matched_terms: Counter[str] = Counter()

        for row in rows:
            request_payload = self._load_usage(row["request_json"])

            routing_payload = request_payload.get("routing")

            if not isinstance(
                routing_payload,
                dict,
            ):
                routing_payload = {}

            mode = routing_payload.get("mode") or request_payload.get("mode")

            if mode == "smart":
                smart_runs += 1
            elif mode == "manual":
                manual_runs += 1

            selected_agent = routing_payload.get(
                "selected_agent_id"
            ) or request_payload.get("agent_id")

            if (
                isinstance(
                    selected_agent,
                    str,
                )
                and selected_agent
            ):
                selected_agents[selected_agent] += 1

            confidence = routing_payload.get("confidence")

            if isinstance(
                confidence,
                (int, float),
            ) and not isinstance(
                confidence,
                bool,
            ):
                confidence_total += float(confidence)
                confidence_count += 1

            routing_latency = routing_payload.get("routing_latency_ms")

            if isinstance(
                routing_latency,
                (int, float),
            ) and not isinstance(
                routing_latency,
                bool,
            ):
                routing_latency_total += float(routing_latency)
                routing_latency_count += 1

            terms = routing_payload.get("matched_terms")

            if isinstance(
                terms,
                list,
            ):
                for term in terms:
                    if not isinstance(
                        term,
                        str,
                    ):
                        continue

                    normalized_term = term.strip().lower()

                    if normalized_term:
                        matched_terms[normalized_term] += 1

        routed_runs = smart_runs + manual_runs

        smart_routing_percentage = self._percentage(
            smart_runs,
            routed_runs,
        )

        average_confidence = (
            confidence_total / confidence_count if confidence_count else 0.0
        )

        average_routing_latency_ms = (
            routing_latency_total / routing_latency_count
            if routing_latency_count
            else 0.0
        )

        agent_selection_distribution = dict(
            sorted(
                selected_agents.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        )

        top_matched_terms = [
            RoutingMatchedTerm(
                term=term,
                count=count,
            )
            for term, count in sorted(
                matched_terms.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )[:10]
        ]

        most_selected_agent = next(
            iter(agent_selection_distribution),
            None,
        )

        return RoutingAnalytics(
            smart_runs=smart_runs,
            manual_runs=manual_runs,
            smart_routing_percentage=(smart_routing_percentage),
            average_confidence=round(
                average_confidence,
                4,
            ),
            average_routing_latency_ms=round(
                average_routing_latency_ms,
                4,
            ),
            most_selected_agent=(most_selected_agent),
            agent_selection_distribution=(agent_selection_distribution),
            top_matched_terms=(top_matched_terms),
        )

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

        recent_runs: list[RecentAnalyticsRun] = []

        for row in rows:
            usage = self._load_usage(row["usage_json"])

            total_tokens_value = usage.get("total_tokens")

            recent_runs.append(
                RecentAnalyticsRun(
                    run_id=row["run_id"],
                    agent_id=row["agent_id"],
                    objective=row["objective"],
                    model=row["model"],
                    provider=row["provider"],
                    status=row["status"],
                    total_tokens=(
                        self._as_int(total_tokens_value)
                        if total_tokens_value is not None
                        else None
                    ),
                    latency_ms=self._as_float(usage.get("latency_ms")),
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
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


agent_analytics_repository = AgentAnalyticsRepository(history_database)
