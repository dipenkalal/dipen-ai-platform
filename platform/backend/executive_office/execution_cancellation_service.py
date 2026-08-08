import hashlib
import json
from typing import Any

from executive_office.execution_cancellation_repository import (
    CancellationStateConflictError,
    ExecutiveExecutionCancellationRepository,
    executive_execution_cancellation_repository,
)
from executive_office.execution_cancellation_schemas import (
    ExecutiveRunningCancellationRecord,
    ExecutiveRunningCancellationRequest,
)
from executive_office.execution_start_repository import (
    ExecutiveExecutionStartRepository,
    executive_execution_start_repository,
)


class ExecutiveExecutionCancellationService:
    def __init__(
        self,
        *,
        cancellation_repository: ExecutiveExecutionCancellationRepository = (
            executive_execution_cancellation_repository
        ),
        start_repository: ExecutiveExecutionStartRepository = (
            executive_execution_start_repository
        ),
    ) -> None:
        self.cancellation_repository = cancellation_repository
        self.start_repository = start_repository

    def request(
        self,
        *,
        execution_id: str,
        request: ExecutiveRunningCancellationRequest,
    ) -> ExecutiveRunningCancellationRecord:
        request_hash = self._request_hash(
            execution_id=execution_id,
            request=request,
        )
        replay = self.cancellation_repository.get_replay(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
        )

        if replay is not None:
            return replay

        authorization = request.owner_authorization
        identity = self.start_repository.get_identity(execution_id)

        if identity is None:
            raise CancellationStateConflictError(
                "The requested execution does not exist."
            )

        if not authorization.approved:
            raise CancellationStateConflictError(
                "Running cancellation authorization is not affirmative."
            )
        if authorization.authorized_by != "dipen-owner":
            raise CancellationStateConflictError(
                "Running cancellation authorization was not issued by Dipen."
            )
        if authorization.execution_id != execution_id:
            raise CancellationStateConflictError(
                "Cancellation authorization is bound to a different execution."
            )
        if authorization.delegation_id != identity.delegation_id:
            raise CancellationStateConflictError(
                "Cancellation authorization is bound to a different delegation."
            )
        if sorted(authorization.child_task_ids) != sorted(
            identity.child_task_ids
        ):
            raise CancellationStateConflictError(
                "Cancellation authorization is bound to a different child task set."
            )

        return self.cancellation_repository.request(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            execution_id=execution_id,
            delegation_id=authorization.delegation_id,
            parent_task_id=authorization.parent_task_id,
            child_task_ids=list(authorization.child_task_ids),
            authorization_id=authorization.authorization_id,
            requested_by=authorization.authorized_by,
            authorization_statement=authorization.statement,
        )

    @staticmethod
    def _request_hash(
        *,
        execution_id: str,
        request: ExecutiveRunningCancellationRequest,
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
                "execution_id": execution_id,
                "owner_authorization": authorization_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


executive_execution_cancellation_service = (
    ExecutiveExecutionCancellationService()
)
