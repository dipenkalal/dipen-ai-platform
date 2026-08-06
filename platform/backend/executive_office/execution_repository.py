from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import (
    ExecutiveDelegationResponse,
    ExecutiveExecutionResponse,
)


class ExecutiveExecutionRepository:
    def __init__(
        self,
        truth_repository: AgentTruthRepository,
    ) -> None:
        self.truth_repository = truth_repository
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS executive_execution_admissions (
                    idempotency_key TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL UNIQUE,
                    delegation_id TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_admissions_delegation_id
                ON executive_execution_admissions(delegation_id)
                """
            )
            connection.commit()

    def get_delegation(
        self,
        delegation_id: str,
    ) -> ExecutiveDelegationResponse | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT response_json
                FROM executive_delegations
                WHERE delegation_id = ?
                """,
                (delegation_id,),
            ).fetchone()

        if row is None:
            return None

        return ExecutiveDelegationResponse.model_validate_json(
            str(row["response_json"])
        )

    def get_replay(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> ExecutiveExecutionResponse | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_execution_admissions
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

        if row is None:
            return None

        if str(row["request_hash"]) != request_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different "
                "Executive Office execution request."
            )

        stored = ExecutiveExecutionResponse.model_validate_json(
            str(row["response_json"])
        )
        return stored.model_copy(
            update={
                "disposition": "idempotent_replay",
                "idempotent_replay": True,
                "message": (
                    "Existing execution admission returned without repeating "
                    "policy, worker, reservation, or executor activity."
                ),
            }
        )

    def persist(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionResponse,
    ) -> ExecutiveExecutionResponse:
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_execution_admissions
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if row is not None:
                if str(row["request_hash"]) != request_hash:
                    connection.rollback()
                    raise IdempotencyConflictError(
                        "The idempotency key is already bound to a different "
                        "Executive Office execution request."
                    )

                stored = ExecutiveExecutionResponse.model_validate_json(
                    str(row["response_json"])
                )
                connection.commit()
                return stored.model_copy(
                    update={
                        "disposition": "idempotent_replay",
                        "idempotent_replay": True,
                        "message": (
                            "Existing execution admission returned without "
                            "repeating policy, worker, reservation, or executor "
                            "activity."
                        ),
                    }
                )

            connection.execute(
                """
                INSERT INTO executive_execution_admissions (
                    idempotency_key,
                    execution_id,
                    delegation_id,
                    request_hash,
                    response_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    response.execution_id,
                    response.delegation_id,
                    request_hash,
                    response.model_dump_json(),
                    response.generated_at.isoformat(),
                ),
            )
            connection.commit()

        return response


executive_execution_repository = ExecutiveExecutionRepository(
    agent_truth_repository
)
