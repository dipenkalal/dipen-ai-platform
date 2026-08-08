from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agents.truth_schemas import (
    TaskLedgerRecord,
    TaskLedgerStatus,
)
from executive_office.schemas import utc_now

ExecutionStartDisposition = Literal[
    "started",
    "completed",
    "failed",
    "manual_review",
    "authorization_required",
    "state_conflict",
    "idempotent_replay",
]
ExecutionStartState = Literal[
    "claimed",
    "reserved",
    "running",
    "completed",
    "failed",
    "manual_review",
    "rejected",
]
ExecutionStatusState = Literal[
    "requested",
    "validated",
    "reserved",
    "running",
    "completed",
    "failed",
    "cancelled",
    "manual_review",
    "rejected",
]
ExecutionTaskResultStatus = Literal["completed", "failed"]
AcceptanceEvidenceSource = Literal["agent-result"]


class OwnerExecutionStartAuthorization(BaseModel):
    authorization_id: str = Field(min_length=4, max_length=160)
    execution_id: str = Field(min_length=4, max_length=160)
    delegation_id: str = Field(min_length=4, max_length=160)
    child_task_ids: list[str] = Field(min_length=1, max_length=6)
    authorized_by: Literal["dipen-owner"] = "dipen-owner"
    approved: bool = True
    scope: Literal["start_reserved_execution"] = (
        "start_reserved_execution"
    )
    statement: str = Field(min_length=4, max_length=2000)
    authorized_at: datetime = Field(default_factory=utc_now)


class ExecutiveExecutionStartRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)
    owner_authorization: OwnerExecutionStartAuthorization


class ExecutiveTaskExecutionResult(BaseModel):
    task_id: str
    agent_id: str
    run_id: str
    status: ExecutionTaskResultStatus
    answer: str
    started_at: datetime
    completed_at: datetime


class ExecutiveTaskAcceptanceEvidence(BaseModel):
    evidence_id: str
    task_id: str
    agent_id: str
    run_id: str
    source: AcceptanceEvidenceSource = "agent-result"
    terminal_status: ExecutionTaskResultStatus
    output_sha256: str = Field(min_length=64, max_length=64)
    accepted: bool = True
    detail: str
    recorded_at: datetime = Field(default_factory=utc_now)


class ExecutiveExecutionStartResponse(BaseModel):
    execution_id: str
    delegation_id: str
    child_task_ids: list[str]
    generated_at: datetime = Field(default_factory=utc_now)
    disposition: ExecutionStartDisposition
    state: ExecutionStartState
    task_results: list[ExecutiveTaskExecutionResult] = Field(
        default_factory=list
    )
    acceptance_evidence: list[ExecutiveTaskAcceptanceEvidence] = Field(
        default_factory=list
    )
    parent_task_status: TaskLedgerStatus | None = None
    execution_started: bool = False
    reservation_released: bool = False
    broker_activated: bool = False
    idempotent_replay: bool = False
    message: str


class ExecutiveExecutionStatusResponse(BaseModel):
    execution_id: str
    delegation_id: str
    state: ExecutionStatusState
    generated_at: datetime = Field(default_factory=utc_now)
    parent_task: TaskLedgerRecord
    child_tasks: list[TaskLedgerRecord]
    active_reservation_ids: list[str] = Field(default_factory=list)
    task_results: list[ExecutiveTaskExecutionResult] = Field(
        default_factory=list
    )
    acceptance_evidence: list[ExecutiveTaskAcceptanceEvidence] = Field(
        default_factory=list
    )
    broker_activated: bool = False
