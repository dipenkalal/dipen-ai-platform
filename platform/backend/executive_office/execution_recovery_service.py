import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal, cast

from agents.truth_schemas import TaskLedgerRecord, TaskLedgerStatus
from agents.truth_service import AgentTruthService, agent_truth_service
from company.catalog import company_registry
from executive_office.execution_recovery_repository import (
    ExecutionControlStateConflictError,
    ExecutionRecoverySnapshot,
    ExecutiveExecutionRecoveryRepository,
    executive_execution_recovery_repository,
)
from executive_office.execution_recovery_schemas import (
    ExecutionControlAction,
    ExecutionControlDisposition,
    ExecutionControlEvidence,
    ExecutiveExecutionControlRequest,
    ExecutiveExecutionControlResponse,
    OwnerExecutionControlAuthorization,
)
from executive_office.execution_start_schemas import (
    ExecutionStatusState,
    ExecutiveExecutionStartResponse,
)
from executive_office.execution_start_service import (
    ExecutiveExecutionStartService,
    executive_execution_start_service,
)
from executive_office.schemas import (
    ExecutiveOfficeCapability,
    ExecutiveOfficeStatusResponse,
)

RecoveryTerminalState = Literal[
    "completed",
    "failed",
    "manual_review",
]


class ExecutiveExecutionRecoveryService:
    version = "0.7.0"
    recovery_grace_seconds = 120.0

    def __init__(
        self,
        *,
        start_service: ExecutiveExecutionStartService = (
            executive_execution_start_service
        ),
        truth_service: AgentTruthService = agent_truth_service,
        recovery_repository: ExecutiveExecutionRecoveryRepository = (
            executive_execution_recovery_repository
        ),
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.start_service = start_service
        self.truth_service = truth_service
        self.recovery_repository = recovery_repository
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    def status(self) -> ExecutiveOfficeStatusResponse:
        start_status = self.start_service.status()
        guardian_role = company_registry.get_role("guardian-ceo")
        capability = ExecutiveOfficeCapability(
            service_id="execution-cancellation-and-recovery",
            acting_role_id="guardian-ceo",
            registry_employment_status=guardian_role.employment_status,
            mode="execution_admission",
            description=(
                "Cancel reserved executions before the start claim and "
                "reconcile interrupted execution state from durable task, "
                "reservation, heartbeat, and acceptance evidence without "
                "replaying an agent or activating the broker."
            ),
        )
        return start_status.model_copy(
            update={
                "version": self.version,
                "execution_cancellation_enabled": True,
                "execution_recovery_enabled": True,
                "broker_activation_enabled": False,
                "capabilities": [
                    *start_status.capabilities,
                    capability,
                ],
            }
        )

    def cancel(
        self,
        *,
        execution_id: str,
        request: ExecutiveExecutionControlRequest,
    ) -> ExecutiveExecutionControlResponse:
        request_hash = self._request_hash(
            action="cancel",
            execution_id=execution_id,
            request=request,
        )
        replay = self.recovery_repository.get_replay(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
        )

        if replay is not None:
            return replay

        snapshot = self.recovery_repository.get_snapshot(execution_id)

        if snapshot is None:
            return self._persist_unknown(
                action="cancel",
                execution_id=execution_id,
                request=request,
                request_hash=request_hash,
            )

        authorization_error = self._authorization_error(
            authorization=request.owner_authorization,
            snapshot=snapshot,
            execution_id=execution_id,
            expected_scope="cancel_reserved_execution",
        )

        if authorization_error is not None:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="cancel",
                    snapshot=snapshot,
                    disposition="authorization_required",
                    state=cast(ExecutionStatusState, snapshot.state),
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="owner-authorization",
                            detail=authorization_error,
                        )
                    ],
                    message=(
                        "Cancellation requires an affirmative owner "
                        "authorization bound to this exact reserved execution."
                    ),
                ),
            )

        if snapshot.state == "cancelled":
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="cancel",
                    snapshot=snapshot,
                    disposition="no_action",
                    state="cancelled",
                    message=(
                        "Execution is already cancelled; no task, reservation, "
                        "agent, or broker action was repeated."
                    ),
                ),
            )

        if snapshot.state != "reserved" or snapshot.validation_only:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="cancel",
                    snapshot=snapshot,
                    disposition="state_conflict",
                    state=cast(ExecutionStatusState, snapshot.state),
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="cancellation-boundary",
                            detail=(
                                "Only a durable reserved execution that has not "
                                "crossed the start-claim boundary can be "
                                "cancelled."
                            ),
                        )
                    ],
                    message=(
                        "Execution cannot be force-cancelled in its current "
                        "state. Running work must be reconciled, not killed or "
                        "replayed."
                    ),
                ),
            )

        if snapshot.start_idempotency_key is not None:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="cancel",
                    snapshot=snapshot,
                    disposition="state_conflict",
                    state=cast(ExecutionStatusState, snapshot.state),
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="start-claim",
                            detail=(
                                "A start claim already exists, so cancellation "
                                "will not cross the execution boundary."
                            ),
                        )
                    ],
                    message=(
                        "Execution has a start claim and will not be "
                        "force-cancelled."
                    ),
                ),
            )

        response = self._response(
            action="cancel",
            snapshot=snapshot,
            disposition="cancelled",
            state="cancelled",
            parent_task_status="manual_review",
            active_reservation_ids=[],
            reservation_released=True,
            evidence=[
                ExecutionControlEvidence(
                    check_id="cancellation-boundary",
                    detail=(
                        "The execution was still reserved and had no start "
                        "claim."
                    ),
                ),
                ExecutionControlEvidence(
                    check_id="broker-isolation",
                    detail=(
                        "Cancellation does not invoke an agent, shell, "
                        "privileged action, or broker."
                    ),
                ),
            ],
            message=(
                "Reserved execution cancelled before agent start. Selected "
                "queued tasks were cancelled, reservations were released, and "
                "the parent moved to manual review."
            ),
        )

        try:
            return self.recovery_repository.cancel_reserved(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=response,
                snapshot=snapshot,
            )
        except ExecutionControlStateConflictError as error:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="cancel",
                    snapshot=snapshot,
                    disposition="state_conflict",
                    state=cast(ExecutionStatusState, snapshot.state),
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="atomic-cancellation",
                            detail=str(error),
                        )
                    ],
                    message=(
                        "Cancellation lost an atomic state race and performed "
                        "no partial execution-control transition."
                    ),
                ),
            )

    def recover(
        self,
        *,
        execution_id: str,
        request: ExecutiveExecutionControlRequest,
    ) -> ExecutiveExecutionControlResponse:
        request_hash = self._request_hash(
            action="recover",
            execution_id=execution_id,
            request=request,
        )
        replay = self.recovery_repository.get_replay(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
        )

        if replay is not None:
            return replay

        snapshot = self.recovery_repository.get_snapshot(execution_id)

        if snapshot is None:
            return self._persist_unknown(
                action="recover",
                execution_id=execution_id,
                request=request,
                request_hash=request_hash,
            )

        authorization_error = self._authorization_error(
            authorization=request.owner_authorization,
            snapshot=snapshot,
            execution_id=execution_id,
            expected_scope="recover_interrupted_execution",
        )

        if authorization_error is not None:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="authorization_required",
                    state=cast(ExecutionStatusState, snapshot.state),
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="owner-authorization",
                            detail=authorization_error,
                        )
                    ],
                    message=(
                        "Recovery requires an affirmative owner authorization "
                        "bound to this exact execution."
                    ),
                ),
            )

        if snapshot.state in {
            "completed",
            "failed",
            "cancelled",
        }:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="no_action",
                    state=cast(ExecutionStatusState, snapshot.state),
                    message=(
                        "Execution is already terminal. Recovery will not "
                        "repeat an agent or alter the terminal outcome."
                    ),
                ),
            )

        if snapshot.state == "reserved":
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="no_action",
                    state="reserved",
                    message=(
                        "Execution is reserved but has not started. Use the "
                        "separate start or cancellation control instead of "
                        "recovery."
                    ),
                ),
            )

        tasks, task_error = self._tasks_for_snapshot(snapshot)

        if task_error is not None:
            return self._finalize_manual_review(
                request=request,
                request_hash=request_hash,
                snapshot=snapshot,
                evidence=[
                    ExecutionControlEvidence(
                        check_id="task-identity",
                        detail=task_error,
                    )
                ],
                message=(
                    "Recovery found inconsistent durable task identity and "
                    "moved the execution to manual review without replay."
                ),
                freeze_nonterminal=False,
            )

        assert tasks is not None

        accepted, acceptance_detail = self._accepted_completion(
            snapshot=snapshot,
        )

        if accepted:
            return self._finalize(
                request=request,
                request_hash=request_hash,
                snapshot=snapshot,
                target_state="completed",
                disposition="recovered",
                release_reservations=True,
                freeze_nonterminal=False,
                evidence=[
                    ExecutionControlEvidence(
                        check_id="acceptance-evidence",
                        detail=acceptance_detail,
                    )
                ],
                message=(
                    "Recovery verified complete cryptographically matched "
                    "acceptance evidence and finalized the execution without "
                    "replaying any agent."
                ),
            )

        if snapshot.state == "manual_review":
            if snapshot.active_reservation_ids:
                return self._finalize(
                    request=request,
                    request_hash=request_hash,
                    snapshot=snapshot,
                    target_state="manual_review",
                    disposition="manual_review",
                    release_reservations=True,
                    freeze_nonterminal=False,
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="manual-review-cleanup",
                            detail=(
                                "Manual-review execution retained active "
                                "reservations. Recovery released them without "
                                "changing the uncertain outcome."
                            ),
                        ),
                        ExecutionControlEvidence(
                            check_id="acceptance-evidence",
                            detail=acceptance_detail,
                        ),
                    ],
                    message=(
                        "Manual-review state retained; stale reservations were "
                        "released and no agent was replayed."
                    ),
                )

            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="no_action",
                    state="manual_review",
                    parent_task_status=self._parent_status(snapshot),
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="acceptance-evidence",
                            detail=acceptance_detail,
                        )
                    ],
                    message=(
                        "Execution is already isolated in manual review with no "
                        "active reservations. Owner review remains required."
                    ),
                ),
            )

        if snapshot.state != "running":
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="state_conflict",
                    state=cast(ExecutionStatusState, snapshot.state),
                    message=(
                        "Recovery only reconciles interrupted running or "
                        "manual-review executions."
                    ),
                ),
            )

        fresh_active_tasks = self._fresh_active_tasks(snapshot)

        if fresh_active_tasks:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="recovery_deferred",
                    state="running",
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="runtime-heartbeat",
                            detail=(
                                "Fresh busy heartbeat still reports active "
                                "selected task(s): "
                                + ", ".join(fresh_active_tasks)
                                + "."
                            ),
                        )
                    ],
                    message=(
                        "Recovery deferred because live runtime evidence still "
                        "shows bounded work in progress."
                    ),
                ),
            )

        claim_age = self._claim_age_seconds(snapshot)

        if (
            claim_age is not None
            and claim_age < self.recovery_grace_seconds
        ):
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="recovery_deferred",
                    state="running",
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="recovery-grace",
                            detail=(
                                f"The start claim is only {claim_age:.1f} "
                                "seconds old; the recovery grace window is "
                                f"{self.recovery_grace_seconds:.0f} seconds."
                            ),
                        )
                    ],
                    message=(
                        "Recovery deferred during the bounded start grace "
                        "window. No execution was replayed."
                    ),
                ),
            )

        statuses = {task.status for task in tasks}

        if statuses <= {"completed", "failed"} and "failed" in statuses:
            return self._finalize(
                request=request,
                request_hash=request_hash,
                snapshot=snapshot,
                target_state="failed",
                disposition="recovered",
                release_reservations=True,
                freeze_nonterminal=False,
                evidence=[
                    ExecutionControlEvidence(
                        check_id="terminal-task-state",
                        detail=(
                            "Every selected task is terminal and at least one "
                            "task is deterministically failed."
                        ),
                    ),
                    ExecutionControlEvidence(
                        check_id="acceptance-evidence",
                        detail=acceptance_detail,
                    ),
                ],
                message=(
                    "Recovery finalized a deterministic failed outcome and "
                    "released reservations without replaying an agent."
                ),
            )

        if statuses == {"completed"}:
            return self._finalize_manual_review(
                request=request,
                request_hash=request_hash,
                snapshot=snapshot,
                evidence=[
                    ExecutionControlEvidence(
                        check_id="terminal-task-state",
                        detail=(
                            "All selected tasks report completed, but durable "
                            "acceptance evidence is incomplete or mismatched."
                        ),
                    ),
                    ExecutionControlEvidence(
                        check_id="acceptance-evidence",
                        detail=acceptance_detail,
                    ),
                ],
                message=(
                    "Completed task state was not enough to prove acceptance. "
                    "Execution moved to manual review without replay."
                ),
                freeze_nonterminal=False,
            )

        return self._finalize_manual_review(
            request=request,
            request_hash=request_hash,
            snapshot=snapshot,
            evidence=[
                ExecutionControlEvidence(
                    check_id="interrupted-runtime",
                    detail=(
                        "No fresh matching busy heartbeat exists after the "
                        "recovery grace window, while selected task state is "
                        "still nonterminal or mixed."
                    ),
                ),
                ExecutionControlEvidence(
                    check_id="no-replay",
                    detail=(
                        "Ambiguous work is frozen for owner review instead of "
                        "being automatically executed again."
                    ),
                ),
            ],
            message=(
                "Interrupted execution could not be proven complete or failed. "
                "Nonterminal selected tasks were frozen in manual review, "
                "reservations were released, and no agent was replayed."
            ),
            freeze_nonterminal=True,
        )

    def _finalize_manual_review(
        self,
        *,
        request: ExecutiveExecutionControlRequest,
        request_hash: str,
        snapshot: ExecutionRecoverySnapshot,
        evidence: list[ExecutionControlEvidence],
        message: str,
        freeze_nonterminal: bool,
    ) -> ExecutiveExecutionControlResponse:
        return self._finalize(
            request=request,
            request_hash=request_hash,
            snapshot=snapshot,
            target_state="manual_review",
            disposition="manual_review",
            release_reservations=True,
            freeze_nonterminal=freeze_nonterminal,
            evidence=evidence,
            message=message,
        )

    def _finalize(
        self,
        *,
        request: ExecutiveExecutionControlRequest,
        request_hash: str,
        snapshot: ExecutionRecoverySnapshot,
        target_state: RecoveryTerminalState,
        disposition: ExecutionControlDisposition,
        release_reservations: bool,
        freeze_nonterminal: bool,
        evidence: list[ExecutionControlEvidence],
        message: str,
    ) -> ExecutiveExecutionControlResponse:
        parent_status: TaskLedgerStatus = (
            "completed"
            if target_state == "completed"
            else "manual_review"
        )
        response = self._response(
            action="recover",
            snapshot=snapshot,
            disposition=disposition,
            state=target_state,
            parent_task_status=parent_status,
            active_reservation_ids=(
                []
                if release_reservations
                else list(snapshot.active_reservation_ids)
            ),
            reservation_released=(
                release_reservations
                and bool(snapshot.active_reservation_ids)
            ),
            evidence=evidence,
            message=message,
        )
        start_response = self._recovered_start_response(
            snapshot=snapshot,
            target_state=target_state,
            parent_status=parent_status,
            reservations_released=release_reservations,
            message=message,
        )

        try:
            return self.recovery_repository.finalize_recovery(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=response,
                snapshot=snapshot,
                start_response=start_response,
                target_state=target_state,
                release_reservations=release_reservations,
                freeze_nonterminal=freeze_nonterminal,
            )
        except ExecutionControlStateConflictError as error:
            return self._persist_response(
                request=request,
                request_hash=request_hash,
                response=self._response(
                    action="recover",
                    snapshot=snapshot,
                    disposition="state_conflict",
                    state=cast(ExecutionStatusState, snapshot.state),
                    evidence=[
                        ExecutionControlEvidence(
                            check_id="atomic-recovery",
                            detail=str(error),
                        )
                    ],
                    message=(
                        "Recovery lost an atomic state race and did not replay "
                        "the execution."
                    ),
                ),
            )

    def _tasks_for_snapshot(
        self,
        snapshot: ExecutionRecoverySnapshot,
    ) -> tuple[list[TaskLedgerRecord] | None, str | None]:
        tasks: list[TaskLedgerRecord] = []

        if not (
            len(snapshot.child_task_ids)
            == len(snapshot.selected_agent_ids)
            == len(snapshot.reservation_ids)
        ):
            return None, "Execution task, agent, and reservation mapping differs."

        for task_id, agent_id in zip(
            snapshot.child_task_ids,
            snapshot.selected_agent_ids,
            strict=True,
        ):
            try:
                task = self.truth_service.get_task(task_id)
            except KeyError:
                return None, f"Selected task {task_id} is missing."

            if (
                task.source_run_id != snapshot.delegation_id
                or task.parent_task_id != snapshot.parent_task_id
                or task.assigned_agent_ids != [agent_id]
            ):
                return (
                    None,
                    (
                        f"Selected task {task_id} no longer matches its execution "
                        "identity."
                    ),
                )
            tasks.append(task)

        return tasks, None

    def _accepted_completion(
        self,
        *,
        snapshot: ExecutionRecoverySnapshot,
    ) -> tuple[bool, str]:
        stored = snapshot.start_response

        if stored is None:
            return False, "No stored execution-start result evidence is available."

        results = {
            result.task_id: result
            for result in stored.task_results
        }
        evidence = {
            item.task_id: item
            for item in stored.acceptance_evidence
        }

        if (
            set(results) != set(snapshot.child_task_ids)
            or set(evidence) != set(snapshot.child_task_ids)
        ):
            return (
                False,
                "Stored result or acceptance-evidence coverage is incomplete.",
            )

        for task_id, agent_id in zip(
            snapshot.child_task_ids,
            snapshot.selected_agent_ids,
            strict=True,
        ):
            result = results[task_id]
            item = evidence[task_id]
            output_hash = hashlib.sha256(
                result.answer.encode()
            ).hexdigest()
            valid = (
                result.agent_id == agent_id
                and result.status == "completed"
                and bool(result.answer.strip())
                and item.agent_id == agent_id
                and item.run_id == result.run_id
                and item.terminal_status == "completed"
                and item.accepted
                and item.output_sha256 == output_hash
            )

            if not valid:
                return (
                    False,
                    (
                        f"Acceptance evidence for {task_id} does not match the "
                        "completed agent result."
                    ),
                )

        return (
            True,
            (
                "Every selected task has completed output with matching agent, "
                "run ID, acceptance flag, terminal status, and SHA-256 evidence."
            ),
        )

    def _fresh_active_tasks(
        self,
        snapshot: ExecutionRecoverySnapshot,
    ) -> list[str]:
        active: list[str] = []

        for task_id, agent_id in zip(
            snapshot.child_task_ids,
            snapshot.selected_agent_ids,
            strict=True,
        ):
            try:
                state = self.truth_service.get_agent_state(agent_id)
            except KeyError:
                continue

            if (
                state.runtime_status == "busy"
                and state.current_task_id == task_id
            ):
                active.append(task_id)

        return active

    def _claim_age_seconds(
        self,
        snapshot: ExecutionRecoverySnapshot,
    ) -> float | None:
        if snapshot.start_updated_at is None:
            return None

        now = self._now()
        return max(
            (now - snapshot.start_updated_at).total_seconds(),
            0.0,
        )

    def _recovered_start_response(
        self,
        *,
        snapshot: ExecutionRecoverySnapshot,
        target_state: RecoveryTerminalState,
        parent_status: TaskLedgerStatus,
        reservations_released: bool,
        message: str,
    ) -> ExecutiveExecutionStartResponse:
        stored = snapshot.start_response
        task_results = stored.task_results if stored is not None else []
        acceptance_evidence = (
            stored.acceptance_evidence
            if stored is not None
            else []
        )
        return ExecutiveExecutionStartResponse(
            execution_id=snapshot.execution_id,
            delegation_id=snapshot.delegation_id,
            child_task_ids=list(snapshot.child_task_ids),
            generated_at=self._now(),
            disposition=target_state,
            state=target_state,
            task_results=task_results,
            acceptance_evidence=acceptance_evidence,
            parent_task_status=parent_status,
            execution_started=True,
            reservation_released=reservations_released,
            broker_activated=False,
            message=message,
        )

    def _parent_status(
        self,
        snapshot: ExecutionRecoverySnapshot,
    ) -> TaskLedgerStatus | None:
        try:
            return self.truth_service.get_task(
                snapshot.parent_task_id
            ).status
        except KeyError:
            return None

    @staticmethod
    def _authorization_error(
        *,
        authorization: OwnerExecutionControlAuthorization,
        snapshot: ExecutionRecoverySnapshot,
        execution_id: str,
        expected_scope: str,
    ) -> str | None:
        if not authorization.approved:
            return "The execution-control authorization is not affirmative."
        if authorization.authorized_by != "dipen-owner":
            return "The execution-control authorization was not issued by Dipen."
        if authorization.scope != expected_scope:
            return "The execution-control authorization has the wrong purpose."
        if authorization.execution_id != execution_id:
            return "The authorization is bound to a different execution."
        if authorization.delegation_id != snapshot.delegation_id:
            return "The authorization is bound to a different delegation."
        if authorization.parent_task_id != snapshot.parent_task_id:
            return "The authorization is bound to a different parent task."
        if sorted(authorization.child_task_ids) != sorted(
            snapshot.child_task_ids
        ):
            return "The authorization is bound to a different child task set."

        return None

    @staticmethod
    def _request_hash(
        *,
        action: ExecutionControlAction,
        execution_id: str,
        request: ExecutiveExecutionControlRequest,
    ) -> str:
        authorization = request.owner_authorization
        authorization_payload: dict[str, Any] = {
            "authorization_id": authorization.authorization_id,
            "execution_id": authorization.execution_id,
            "delegation_id": authorization.delegation_id,
            "parent_task_id": authorization.parent_task_id,
            "child_task_ids": sorted(authorization.child_task_ids),
            "authorized_by": authorization.authorized_by,
            "approved": authorization.approved,
            "scope": authorization.scope,
            "statement": authorization.statement,
        }
        canonical = json.dumps(
            {
                "action": action,
                "execution_id": execution_id,
                "owner_authorization": authorization_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _persist_unknown(
        self,
        *,
        action: ExecutionControlAction,
        execution_id: str,
        request: ExecutiveExecutionControlRequest,
        request_hash: str,
    ) -> ExecutiveExecutionControlResponse:
        response = ExecutiveExecutionControlResponse(
            execution_id=execution_id,
            delegation_id=request.owner_authorization.delegation_id,
            parent_task_id=request.owner_authorization.parent_task_id,
            child_task_ids=list(
                request.owner_authorization.child_task_ids
            ),
            action=action,
            generated_at=self._now(),
            disposition="state_conflict",
            state="rejected",
            evidence=[
                ExecutionControlEvidence(
                    check_id="execution-identity",
                    detail="The requested execution does not exist.",
                )
            ],
            message=(
                "Execution control rejected for an unknown execution. "
                "No runtime action was attempted."
            ),
        )
        return self._persist_response(
            request=request,
            request_hash=request_hash,
            response=response,
        )

    def _persist_response(
        self,
        *,
        request: ExecutiveExecutionControlRequest,
        request_hash: str,
        response: ExecutiveExecutionControlResponse,
    ) -> ExecutiveExecutionControlResponse:
        return self.recovery_repository.persist(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            response=response,
        )

    def _response(
        self,
        *,
        action: ExecutionControlAction,
        snapshot: ExecutionRecoverySnapshot,
        disposition: ExecutionControlDisposition,
        state: ExecutionStatusState,
        message: str,
        parent_task_status: TaskLedgerStatus | None = None,
        active_reservation_ids: list[str] | None = None,
        evidence: list[ExecutionControlEvidence] | None = None,
        reservation_released: bool = False,
    ) -> ExecutiveExecutionControlResponse:
        return ExecutiveExecutionControlResponse(
            execution_id=snapshot.execution_id,
            delegation_id=snapshot.delegation_id,
            parent_task_id=snapshot.parent_task_id,
            child_task_ids=list(snapshot.child_task_ids),
            action=action,
            generated_at=self._now(),
            disposition=disposition,
            state=state,
            parent_task_status=parent_task_status,
            active_reservation_ids=(
                list(snapshot.active_reservation_ids)
                if active_reservation_ids is None
                else active_reservation_ids
            ),
            evidence=evidence or [],
            reservation_released=reservation_released,
            execution_replayed=False,
            broker_activated=False,
            message=message,
        )

    def _now(self) -> datetime:
        value = self.now_provider()

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)


executive_execution_recovery_service = (
    ExecutiveExecutionRecoveryService()
)
