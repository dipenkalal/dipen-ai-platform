from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from executive_office.schemas import utc_now

CancellationRequestState = Literal[
    "requested",
    "observed",
    "resolved",
]


class OwnerRunningCancellationAuthorization(BaseModel):
    authorization_id: str = Field(min_length=4, max_length=160)
    execution_id: str = Field(min_length=4, max_length=160)
    delegation_id: str = Field(min_length=4, max_length=160)
    parent_task_id: str = Field(min_length=4, max_length=160)
    child_task_ids: list[str] = Field(min_length=1, max_length=6)
    authorized_by: Literal["dipen-owner"] = "dipen-owner"
    approved: bool = True
    scope: Literal["request_running_execution_cancellation"] = (
        "request_running_execution_cancellation"
    )
    statement: str = Field(min_length=4, max_length=2000)
    authorized_at: datetime = Field(default_factory=utc_now)


class ExecutiveRunningCancellationRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)
    owner_authorization: OwnerRunningCancellationAuthorization


class ExecutiveRunningCancellationRecord(BaseModel):
    cancellation_id: str
    execution_id: str
    delegation_id: str
    parent_task_id: str
    child_task_ids: list[str]
    authorization_id: str
    requested_by: Literal["dipen-owner"] = "dipen-owner"
    state: CancellationRequestState
    requested_at: datetime = Field(default_factory=utc_now)
    observed_at: datetime | None = None
    resolved_at: datetime | None = None
    idempotent_replay: bool = False
    message: str
