from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agents.truth_schemas import TaskLedgerStatus
from executive_office.execution_start_schemas import ExecutionStatusState
from executive_office.schemas import utc_now

ExecutionControlAction = Literal["cancel", "recover"]
ExecutionControlDisposition = Literal[
    "cancelled",
    "recovered",
    "manual_review",
    "recovery_deferred",
    "authorization_required",
    "state_conflict",
    "no_action",
    "idempotent_replay",
]


class OwnerExecutionControlAuthorization(BaseModel):
    authorization_id: str = Field(min_length=4, max_length=160)
    execution_id: str = Field(min_length=4, max_length=160)
    delegation_id: str = Field(min_length=4, max_length=160)
    parent_task_id: str = Field(min_length=4, max_length=160)
    child_task_ids: list[str] = Field(min_length=1, max_length=6)
    authorized_by: Literal["dipen-owner"] = "dipen-owner"
    approved: bool = True
    scope: Literal[
        "cancel_reserved_execution",
        "recover_interrupted_execution",
    ]
    statement: str = Field(min_length=4, max_length=2000)
    authorized_at: datetime = Field(default_factory=utc_now)


class ExecutiveExecutionControlRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)
    owner_authorization: OwnerExecutionControlAuthorization


class ExecutionControlEvidence(BaseModel):
    check_id: str = Field(min_length=2, max_length=120)
    detail: str = Field(min_length=2, max_length=2000)


class ExecutiveExecutionControlResponse(BaseModel):
    execution_id: str
    delegation_id: str
    parent_task_id: str
    child_task_ids: list[str]
    action: ExecutionControlAction
    generated_at: datetime = Field(default_factory=utc_now)
    disposition: ExecutionControlDisposition
    state: ExecutionStatusState
    parent_task_status: TaskLedgerStatus | None = None
    active_reservation_ids: list[str] = Field(default_factory=list)
    evidence: list[ExecutionControlEvidence] = Field(default_factory=list)
    reservation_released: bool = False
    execution_replayed: bool = False
    broker_activated: bool = False
    idempotent_replay: bool = False
    message: str
