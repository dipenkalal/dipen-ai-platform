import json
import tempfile
import unittest
from pathlib import Path

from agents.truth_repository import AgentTruthRepository
from executive_office.execution_cancellation_repository import (
    CancellationStateConflictError,
    ExecutiveExecutionCancellationRepository,
)
from executive_office.execution_repository import ExecutiveExecutionRepository
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import utc_now


class ExecutiveExecutionCancellationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "execution-cancellation.db"
        )
        self.truth_repository = AgentTruthRepository(database_path)
        ExecutiveExecutionRepository(self.truth_repository)
        self.repository = ExecutiveExecutionCancellationRepository(
            self.truth_repository
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def seed_execution(
        self,
        *,
        execution_id: str = "execution-001",
        state: str = "running",
        validation_only: bool = False,
    ) -> None:
        now = utc_now().isoformat()

        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO executive_execution_records (
                    execution_id,
                    delegation_id,
                    parent_task_id,
                    child_task_ids_json,
                    authorization_id,
                    authorized_by,
                    authorization_statement,
                    request_hash,
                    selected_agent_ids_json,
                    reservation_ids_json,
                    state,
                    validation_evidence_json,
                    validation_only,
                    requested_at,
                    admitted_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    "delegation-001",
                    "parent-task-001",
                    json.dumps(["child-task-001"]),
                    "execution-authorization-001",
                    "dipen-owner",
                    "Authorize bounded execution.",
                    "execution-request-hash",
                    json.dumps(["system-agent"]),
                    json.dumps(["reservation-001"]),
                    state,
                    "[]",
                    int(validation_only),
                    now,
                    now,
                    now,
                ),
            )
            connection.commit()

    def request_cancellation(
        self,
        *,
        request_hash: str = "cancel-request-hash",
        idempotency_key: str = "cancel-request-0001",
        child_task_ids: list[str] | None = None,
    ):
        return self.repository.request(
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            execution_id="execution-001",
            delegation_id="delegation-001",
            parent_task_id="parent-task-001",
            child_task_ids=child_task_ids or ["child-task-001"],
            authorization_id="cancel-authorization-001",
            requested_by="dipen-owner",
            authorization_statement=(
                "Request cooperative cancellation of the exact running execution."
            ),
        )

    def execution_state(self) -> str:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT state
                FROM executive_execution_records
                WHERE execution_id = 'execution-001'
                """
            ).fetchone()

        assert row is not None
        return str(row["state"])

    def test_request_persists_intent_without_mutating_execution(self) -> None:
        self.seed_execution()

        record = self.request_cancellation()

        self.assertEqual(record.state, "requested")
        self.assertEqual(record.execution_id, "execution-001")
        self.assertEqual(record.requested_by, "dipen-owner")
        self.assertFalse(record.idempotent_replay)
        self.assertIsNone(record.observed_at)
        self.assertIsNone(record.resolved_at)
        self.assertEqual(self.execution_state(), "running")

    def test_same_request_replays_and_changed_hash_conflicts(self) -> None:
        self.seed_execution()
        first = self.request_cancellation()
        replay = self.request_cancellation()

        self.assertEqual(first.cancellation_id, replay.cancellation_id)
        self.assertTrue(replay.idempotent_replay)

        with self.assertRaises(IdempotencyConflictError):
            self.request_cancellation(request_hash="different-request-hash")

    def test_non_running_execution_is_rejected(self) -> None:
        self.seed_execution(state="completed")

        with self.assertRaises(CancellationStateConflictError):
            self.request_cancellation()

        self.assertIsNone(
            self.repository.get_for_execution("execution-001")
        )

    def test_execution_identity_mismatch_is_rejected(self) -> None:
        self.seed_execution()

        with self.assertRaises(CancellationStateConflictError):
            self.request_cancellation(child_task_ids=["different-child"])

    def test_runtime_can_acknowledge_and_resolve_intent(self) -> None:
        self.seed_execution()
        self.request_cancellation()

        observed = self.repository.mark_observed("execution-001")
        resolved = self.repository.mark_resolved("execution-001")

        self.assertEqual(observed.state, "observed")
        self.assertIsNotNone(observed.observed_at)
        self.assertEqual(resolved.state, "resolved")
        self.assertIsNotNone(resolved.observed_at)
        self.assertIsNotNone(resolved.resolved_at)
        self.assertEqual(self.execution_state(), "running")


if __name__ == "__main__":
    unittest.main()
