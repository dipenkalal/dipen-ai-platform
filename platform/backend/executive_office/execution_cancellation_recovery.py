from company.catalog import company_registry
from executive_office.execution_cancellation_reconciliation import (
    ExecutiveExecutionCancellationReconciler,
    executive_execution_cancellation_reconciler,
)
from executive_office.execution_cancellation_repository import (
    ExecutiveExecutionCancellationRepository,
    executive_execution_cancellation_repository,
)
from executive_office.execution_recovery_schemas import (
    ExecutionControlEvidence,
    ExecutiveExecutionControlRequest,
    ExecutiveExecutionControlResponse,
)
from executive_office.execution_recovery_service import (
    ExecutiveExecutionRecoveryService,
    executive_execution_recovery_service,
)
from executive_office.execution_start_repository import ExecutionStartClaim
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartResponse,
)
from executive_office.schemas import (
    ExecutiveOfficeCapability,
    ExecutiveOfficeStatusResponse,
)


class ExecutiveCancellationAwareRecoveryService:
    """Finish an interrupted cooperative cancellation without replaying work."""

    version = "0.10.0"

    def __init__(
        self,
        *,
        recovery_service: ExecutiveExecutionRecoveryService = (
            executive_execution_recovery_service
        ),
        cancellation_repository: ExecutiveExecutionCancellationRepository = (
            executive_execution_cancellation_repository
        ),
        cancellation_reconciler: ExecutiveExecutionCancellationReconciler = (
            executive_execution_cancellation_reconciler
        ),
    ) -> None:
        self.recovery_service = recovery_service
        self.cancellation_repository = cancellation_repository
        self.cancellation_reconciler = cancellation_reconciler

    def status(self) -> ExecutiveOfficeStatusResponse:
        recovery_status = self.recovery_service.status()
        guardian_role = company_registry.get_role("guardian-ceo")
        capability = ExecutiveOfficeCapability(
            service_id="cooperative-running-execution-cancellation",
            acting_role_id="guardian-ceo",
            registry_employment_status=guardian_role.employment_status,
            mode="execution_admission",
            description=(
                "Persist owner-requested cancellation for running bounded work, "
                "observe it at safe child-task checkpoints, stop launching "
                "additional children, and recover interrupted cancellation from "
                "durable state without replay or broker activation."
            ),
        )
        return recovery_status.model_copy(
            update={
                "version": self.version,
                "execution_cancellation_enabled": True,
                "execution_recovery_enabled": True,
                "broker_activation_enabled": False,
                "capabilities": [
                    *recovery_status.capabilities,
                    capability,
                ],
            }
        )

    def recover(
        self,
        *,
        execution_id: str,
        request: ExecutiveExecutionControlRequest,
    ) -> ExecutiveExecutionControlResponse:
        cancellation = self.cancellation_repository.get_for_execution(execution_id)

        if cancellation is None or cancellation.state == "resolved":
            return self.recovery_service.recover(
                execution_id=execution_id,
                request=request,
            )

        snapshot = self.recovery_service.recovery_repository.get_snapshot(execution_id)

        if snapshot is None or snapshot.state != "running":
            return self.recovery_service.recover(
                execution_id=execution_id,
                request=request,
            )

        authorization_error = self.recovery_service._authorization_error(
            authorization=request.owner_authorization,
            snapshot=snapshot,
            execution_id=execution_id,
            expected_scope="recover_interrupted_execution",
        )

        if authorization_error is not None:
            return self.recovery_service.recover(
                execution_id=execution_id,
                request=request,
            )

        if self.recovery_service._fresh_active_tasks(snapshot):
            return self.recovery_service.recover(
                execution_id=execution_id,
                request=request,
            )

        claim_age = self.recovery_service._claim_age_seconds(snapshot)

        if (
            claim_age is not None
            and claim_age < self.recovery_service.recovery_grace_seconds
        ):
            return self.recovery_service.recover(
                execution_id=execution_id,
                request=request,
            )

        if snapshot.start_idempotency_key is None:
            return self.recovery_service.recover(
                execution_id=execution_id,
                request=request,
            )

        if cancellation.state == "requested":
            self.cancellation_repository.mark_observed(execution_id)

        claim = ExecutionStartClaim(
            execution_id=snapshot.execution_id,
            delegation_id=snapshot.delegation_id,
            parent_task_id=snapshot.parent_task_id,
            child_task_ids=snapshot.child_task_ids,
            selected_agent_ids=snapshot.selected_agent_ids,
            reservation_ids=snapshot.reservation_ids,
        )
        stored = snapshot.start_response
        response = ExecutiveExecutionStartResponse(
            execution_id=snapshot.execution_id,
            delegation_id=snapshot.delegation_id,
            child_task_ids=list(snapshot.child_task_ids),
            generated_at=self.recovery_service._now(),
            disposition="cancelled",
            state="cancelled",
            task_results=stored.task_results if stored is not None else [],
            acceptance_evidence=(
                stored.acceptance_evidence if stored is not None else []
            ),
            parent_task_status="manual_review",
            execution_started=True,
            reservation_released=True,
            broker_activated=False,
            message=(
                "Recovery completed a previously requested cooperative "
                "cancellation after live-work and grace checks. No agent was "
                "replayed."
            ),
        )
        self.cancellation_reconciler.finalize_observed(
            claim=claim,
            idempotency_key=snapshot.start_idempotency_key,
            response=response,
        )

        request_hash = self.recovery_service._request_hash(
            action="recover",
            execution_id=execution_id,
            request=request,
        )
        control_response = self.recovery_service._response(
            action="recover",
            snapshot=snapshot,
            disposition="recovered",
            state="cancelled",
            parent_task_status="manual_review",
            active_reservation_ids=[],
            reservation_released=bool(snapshot.active_reservation_ids),
            evidence=[
                ExecutionControlEvidence(
                    check_id="cooperative-cancellation",
                    detail=(
                        "A durable cancellation request existed and no fresh "
                        "selected-task heartbeat remained after the recovery "
                        "grace window."
                    ),
                ),
                ExecutionControlEvidence(
                    check_id="no-replay",
                    detail=(
                        "Recovery finalized cancellation from durable state "
                        "without invoking an agent or broker."
                    ),
                ),
            ],
            message=(
                "Interrupted cooperative cancellation recovered atomically. "
                "Remaining nonterminal child work was cancelled, reservations "
                "were released, and no execution was replayed."
            ),
        )
        return self.recovery_service._persist_response(
            request=request,
            request_hash=request_hash,
            response=control_response,
        )


executive_cancellation_aware_recovery_service = (
    ExecutiveCancellationAwareRecoveryService()
)
