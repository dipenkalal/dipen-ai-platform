import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

_TEST_DATA_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="dap-execution-recovery-tests-")
)
os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY",
    str(_TEST_DATA_DIRECTORY / "knowledge-uploads"),
)
os.environ.setdefault(
    "DAP_AGENT_TRUTH_DB",
    str(_TEST_DATA_DIRECTORY / "global-agent-truth.db"),
)

from agents.registry import agent_registry
from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import AgentHeartbeat
from agents.truth_service import AgentTruthService
from executive_office.delegation_service import ExecutiveDelegationService
from executive_office.execution_recovery_repository import (
    ExecutiveExecutionRecoveryRepository,
)
from executive_office.execution_recovery_schemas import (
    ExecutiveExecutionControlRequest,
    OwnerExecutionControlAuthorization,
)
from executive_office.execution_recovery_service import (
    ExecutiveExecutionRecoveryService,
)
from executive_office.execution_repository import ExecutiveExecutionRepository
from executive_office.execution_reservation_service import (
    ExecutiveReservationService,
)
from executive_office.execution_start_repository import (
    ExecutionStartClaim,
    ExecutiveExecutionStartRepository,
)
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartResponse,
    ExecutiveTaskAcceptanceEvidence,
    ExecutiveTaskExecutionResult,
)
from executive_office.repository import (
    ExecutiveDelegationRepository,
    IdempotencyConflictError,
)
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveExecutionRequest,
    ExecutivePlanRequest,
    OwnerExecutionAuthorization,
)
from executive_office.service import ExecutiveOfficeService


class ExecutiveExecutionRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "execution-recovery.db"
        )
        self.now = datetime(2026, 8, 7, 2, 0, tzinfo=timezone.utc)
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(
            agent_registry,
            self.truth_repository,
            now_provider=lambda: self.now,
        )
        delegation_repository = ExecutiveDelegationRepository(
            self.truth_repository
        )
        self.execution_repository = ExecutiveExecutionRepository(
            self.truth_repository
        )
        self.start_repository = ExecutiveExecutionStartRepository(
            self.truth_repository
        )
        self.recovery_repository = ExecutiveExecutionRecoveryRepository(
            self.truth_repository
        )
        advisory_service = ExecutiveOfficeService()
        self.delegation_service = ExecutiveDelegationService(
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            delegation_repository=delegation_repository,
        )
        self.reservation_service = ExecutiveReservationService(
            delegation_service=self.delegation_service,
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            execution_repository=self.execution_repository,
        )
        self.service = ExecutiveExecutionRecoveryService(
            truth_service=self.truth_service,
            recovery_repository=self.recovery_repository,
            now_provider=lambda: self.now,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def reserve_execution(self, suffix: str):
        delegation = self.delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Research storage upgrade options"]
                ),
                idempotency_key=f"recovery-source-{suffix}",
            )
        )
        self.assertEqual(delegation.disposition, "delegated")
        parent = delegation.parent_task
        assert parent is not None
        child_ids = [task.task_id for task in delegation.child_tasks]
        request = ExecutiveExecutionRequest(
            delegation_id=delegation.delegation_id,
            parent_task_id=parent.task_id,
            child_task_ids=child_ids,
            idempotency_key=f"recovery-reserve-{suffix}",
            validation_only=False,
            owner_authorization=OwnerExecutionAuthorization(
                authorization_id=f"reserve-owner-{suffix}",
                delegation_id=delegation.delegation_id,
                parent_task_id=parent.task_id,
                child_task_ids=child_ids,
                validation_only=False,
                statement=(
                    "Authorize bounded internal task reservation only."
                ),
            ),
        )
        response = self.reservation_service.admit(request)
        self.assertEqual(response.state, "reserved")
        return response

    def claim_execution(self, reservation, suffix: str) -> ExecutionStartClaim:
        claimed = self.start_repository.claim(
            execution_id=reservation.execution_id,
            idempotency_key=f"recovery-start-{suffix}",
            request_hash=f"recovery-start-hash-{suffix}",
        )
        self.assertIsInstance(claimed, ExecutionStartClaim)
        assert isinstance(claimed, ExecutionStartClaim)
        return claimed

    def control_request(
        self,
        reservation,
        *,
        action: str,
        key: str,
        statement: str = "Authorize bounded execution control.",
    ) -> ExecutiveExecutionControlRequest:
        scope = (
            "cancel_reserved_execution"
            if action == "cancel"
            else "recover_interrupted_execution"
        )
        return ExecutiveExecutionControlRequest(
            idempotency_key=key,
            owner_authorization=OwnerExecutionControlAuthorization(
                authorization_id=f"control-owner-{key}",
                execution_id=reservation.execution_id,
                delegation_id=reservation.delegation_id,
                parent_task_id=reservation.parent_task_id,
                child_task_ids=list(reservation.child_task_ids),
                scope=scope,
                statement=statement,
            ),
        )

    def age_start_claim(self, execution_id: str) -> None:
        old = (self.now - timedelta(minutes=10)).isoformat()

        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                UPDATE executive_execution_records
                SET updated_at = ?
                WHERE execution_id = ?
                """,
                (old, execution_id),
            )
            connection.execute(
                """
                UPDATE executive_execution_starts
                SET updated_at = ?
                WHERE execution_id = ?
                """,
                (old, execution_id),
            )
            connection.commit()

    def active_reservation_count(self, execution_id: str) -> int:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM executive_execution_reservations
                WHERE execution_id = ? AND released_at IS NULL
                """,
                (execution_id,),
            ).fetchone()

        assert row is not None
        return int(row["total"])

    def test_cancel_reserved_execution_is_atomic_and_never_runs_agent(self) -> None:
        reservation = self.reserve_execution("cancel-0001")
        child_id = reservation.child_task_ids[0]

        with patch(
            "agents.runtime.instrumented_agent_executor.run"
        ) as executor_run:
            response = self.service.cancel(
                execution_id=reservation.execution_id,
                request=self.control_request(
                    reservation,
                    action="cancel",
                    key="cancel-control-0001",
                ),
            )

        self.assertEqual(response.disposition, "cancelled")
        self.assertEqual(response.state, "cancelled")
        self.assertTrue(response.reservation_released)
        self.assertFalse(response.execution_replayed)
        self.assertFalse(response.broker_activated)
        self.assertEqual(
            self.truth_service.get_task(child_id).status,
            "cancelled",
        )
        self.assertEqual(
            self.truth_service.get_task(
                reservation.parent_task_id
            ).status,
            "manual_review",
        )
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            0,
        )
        executor_run.assert_not_called()

    def test_cancel_replay_is_resolved_before_state_recheck(self) -> None:
        reservation = self.reserve_execution("cancel-replay-0001")
        request = self.control_request(
            reservation,
            action="cancel",
            key="cancel-control-replay-0001",
        )
        first = self.service.cancel(
            execution_id=reservation.execution_id,
            request=request,
        )
        replay = self.service.cancel(
            execution_id=reservation.execution_id,
            request=request,
        )

        self.assertEqual(first.disposition, "cancelled")
        self.assertEqual(replay.disposition, "idempotent_replay")
        self.assertTrue(replay.idempotent_replay)
        self.assertFalse(replay.execution_replayed)

    def test_control_key_reuse_with_changed_request_conflicts(self) -> None:
        reservation = self.reserve_execution("cancel-conflict-0001")
        first = self.control_request(
            reservation,
            action="cancel",
            key="cancel-control-conflict-0001",
            statement="Authorize exact reserved cancellation.",
        )
        second = self.control_request(
            reservation,
            action="cancel",
            key="cancel-control-conflict-0001",
            statement="Different bounded cancellation statement.",
        )
        self.service.cancel(
            execution_id=reservation.execution_id,
            request=first,
        )

        with self.assertRaises(IdempotencyConflictError):
            self.service.cancel(
                execution_id=reservation.execution_id,
                request=second,
            )

    def test_running_execution_is_not_force_cancelled(self) -> None:
        reservation = self.reserve_execution("running-cancel-0001")
        self.claim_execution(reservation, "running-cancel-0001")

        with patch(
            "agents.runtime.instrumented_agent_executor.run"
        ) as executor_run:
            response = self.service.cancel(
                execution_id=reservation.execution_id,
                request=self.control_request(
                    reservation,
                    action="cancel",
                    key="running-cancel-control-0001",
                ),
            )

        self.assertEqual(response.disposition, "state_conflict")
        self.assertEqual(response.state, "running")
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            1,
        )
        self.assertEqual(
            self.truth_service.get_task(
                reservation.child_task_ids[0]
            ).status,
            "queued",
        )
        executor_run.assert_not_called()

    def test_fresh_busy_heartbeat_defers_recovery(self) -> None:
        reservation = self.reserve_execution("busy-recovery-0001")
        self.claim_execution(reservation, "busy-recovery-0001")
        agent_id = reservation.selected_agent_ids[0]
        task_id = reservation.child_task_ids[0]
        self.truth_service.record_heartbeat(
            AgentHeartbeat(
                agent_id=agent_id,
                worker_id="recovery-test-worker",
                status="busy",
                current_task_id=task_id,
                observed_at=self.now,
            )
        )

        response = self.service.recover(
            execution_id=reservation.execution_id,
            request=self.control_request(
                reservation,
                action="recover",
                key="busy-recovery-control-0001",
            ),
        )

        self.assertEqual(response.disposition, "recovery_deferred")
        self.assertEqual(response.state, "running")
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            1,
        )

    def test_ambiguous_stale_running_execution_moves_to_manual_review(self) -> None:
        reservation = self.reserve_execution("ambiguous-recovery-0001")
        self.claim_execution(reservation, "ambiguous-recovery-0001")
        self.age_start_claim(reservation.execution_id)

        with patch(
            "agents.runtime.instrumented_agent_executor.run"
        ) as executor_run:
            response = self.service.recover(
                execution_id=reservation.execution_id,
                request=self.control_request(
                    reservation,
                    action="recover",
                    key="ambiguous-recovery-control-0001",
                ),
            )

        self.assertEqual(response.disposition, "manual_review")
        self.assertEqual(response.state, "manual_review")
        self.assertEqual(
            self.truth_service.get_task(
                reservation.child_task_ids[0]
            ).status,
            "manual_review",
        )
        self.assertEqual(
            self.truth_service.get_task(
                reservation.parent_task_id
            ).status,
            "manual_review",
        )
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            0,
        )
        executor_run.assert_not_called()

    def test_failed_terminal_task_recovers_failed_without_replay(self) -> None:
        reservation = self.reserve_execution("failed-recovery-0001")
        self.claim_execution(reservation, "failed-recovery-0001")
        self.age_start_claim(reservation.execution_id)
        child = self.truth_service.get_task(
            reservation.child_task_ids[0]
        )
        self.truth_service.upsert_task(
            child.model_copy(
                update={
                    "status": "failed",
                    "error": "deterministic test failure",
                    "updated_at": self.now,
                    "completed_at": self.now,
                }
            )
        )

        response = self.service.recover(
            execution_id=reservation.execution_id,
            request=self.control_request(
                reservation,
                action="recover",
                key="failed-recovery-control-0001",
            ),
        )

        self.assertEqual(response.disposition, "recovered")
        self.assertEqual(response.state, "failed")
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            0,
        )
        self.assertEqual(
            self.truth_service.get_task(
                reservation.parent_task_id
            ).status,
            "manual_review",
        )

    def test_completed_task_without_evidence_requires_manual_review(self) -> None:
        reservation = self.reserve_execution("no-evidence-0001")
        self.claim_execution(reservation, "no-evidence-0001")
        self.age_start_claim(reservation.execution_id)
        child = self.truth_service.get_task(
            reservation.child_task_ids[0]
        )
        self.truth_service.upsert_task(
            child.model_copy(
                update={
                    "status": "completed",
                    "progress_percent": 100.0,
                    "updated_at": self.now,
                    "completed_at": self.now,
                }
            )
        )

        response = self.service.recover(
            execution_id=reservation.execution_id,
            request=self.control_request(
                reservation,
                action="recover",
                key="no-evidence-control-0001",
            ),
        )

        self.assertEqual(response.disposition, "manual_review")
        self.assertEqual(response.state, "manual_review")
        self.assertEqual(
            self.truth_service.get_task(
                reservation.parent_task_id
            ).status,
            "manual_review",
        )

    def test_manual_review_with_matching_evidence_recovers_completed(self) -> None:
        reservation = self.reserve_execution("evidence-0001")
        self.claim_execution(reservation, "evidence-0001")
        task_id = reservation.child_task_ids[0]
        agent_id = reservation.selected_agent_ids[0]
        answer = "Validated bounded recovery result."
        run_id = "recovery-agent-run-0001"
        digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
        result = ExecutiveTaskExecutionResult(
            task_id=task_id,
            agent_id=agent_id,
            run_id=run_id,
            status="completed",
            answer=answer,
            started_at=self.now,
            completed_at=self.now,
        )
        evidence = ExecutiveTaskAcceptanceEvidence(
            evidence_id="execution-evidence-recovery-0001",
            task_id=task_id,
            agent_id=agent_id,
            run_id=run_id,
            terminal_status="completed",
            output_sha256=digest,
            accepted=True,
            detail="Validated matching result evidence.",
            recorded_at=self.now,
        )
        child = self.truth_service.get_task(task_id)
        self.truth_service.upsert_task(
            child.model_copy(
                update={
                    "status": "completed",
                    "progress_percent": 100.0,
                    "updated_at": self.now,
                    "completed_at": self.now,
                }
            )
        )
        stored = ExecutiveExecutionStartResponse(
            execution_id=reservation.execution_id,
            delegation_id=reservation.delegation_id,
            child_task_ids=list(reservation.child_task_ids),
            generated_at=self.now,
            disposition="manual_review",
            state="manual_review",
            task_results=[result],
            acceptance_evidence=[evidence],
            execution_started=True,
            reservation_released=False,
            message="Awaiting recovery.",
        )

        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                UPDATE executive_execution_records
                SET state = 'manual_review', updated_at = ?
                WHERE execution_id = ?
                """,
                (self.now.isoformat(), reservation.execution_id),
            )
            connection.execute(
                """
                UPDATE executive_execution_starts
                SET
                    status = 'manual_review',
                    response_json = ?,
                    updated_at = ?
                WHERE execution_id = ?
                """,
                (
                    stored.model_dump_json(),
                    self.now.isoformat(),
                    reservation.execution_id,
                ),
            )
            connection.commit()

        response = self.service.recover(
            execution_id=reservation.execution_id,
            request=self.control_request(
                reservation,
                action="recover",
                key="evidence-recovery-control-0001",
            ),
        )

        self.assertEqual(response.disposition, "recovered")
        self.assertEqual(response.state, "completed")
        self.assertFalse(response.execution_replayed)
        self.assertEqual(
            self.truth_service.get_task(
                reservation.parent_task_id
            ).status,
            "completed",
        )
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            0,
        )


if __name__ == "__main__":
    unittest.main()
