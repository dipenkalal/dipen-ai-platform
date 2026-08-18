from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from agents.truth_schemas import TaskLedgerRecord
from engineering.ruflo_adapter_contract import (
    EngineeringTaskEnvelope,
    RufloAdapterRequest,
)
from executive_office.schemas import ExecutiveExecutionResponse


class RufloHandoffScope(BaseModel):
    """DAP-owned scope added to a canonical Executive Office task."""

    acceptance_criteria: list[str] = Field(min_length=1, max_length=20)
    allowed_paths: list[str] = Field(min_length=1, max_length=40)
    constraints: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("acceptance_criteria", "constraints")
    @classmethod
    def normalize_text_items(cls, items: list[str]) -> list[str]:
        normalized = [item.strip() for item in items]
        if any(not item for item in normalized):
            raise ValueError("handoff text items must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("handoff text items must be unique")
        return normalized

    @field_validator("allowed_paths")
    @classmethod
    def validate_allowed_paths(cls, paths: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for raw_path in paths:
            value = raw_path.strip()
            if (
                not value
                or value.startswith(("/", "~"))
                or "\\" in value
                or ":" in value
            ):
                raise ValueError(
                    "allowed paths must be repository-relative POSIX paths"
                )

            segments = value.split("/")
            if any(segment in {"", ".", ".."} for segment in segments):
                raise ValueError(
                    "allowed paths cannot contain empty, dot, or parent segments"
                )

            canonical = str(PurePosixPath(value))
            if canonical in seen:
                raise ValueError("allowed paths must be unique")
            seen.add(canonical)
            normalized.append(canonical)

        return normalized


class RufloExecutiveHandoff(BaseModel):
    """Evidence that DAP mapped canonical task truth into a Ruflo request."""

    source_execution_id: str
    source_delegation_id: str
    source_parent_task_id: str
    source_task_id: str
    source_task_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request: RufloAdapterRequest
    canonical_task_created: Literal[False] = False
    owner_approval_created: Literal[False] = False
    execution_authority_transferred: Literal[False] = False


class RufloExecutiveHandoffService:
    """Translate DAP-owned task/admission evidence into bounded Ruflo guidance.

    The caller supplies canonical DAP model objects. This service performs no
    repository writes, does not create approvals, and does not invoke Ruflo or
    Codex. Candidate generation remains the responsibility of the separately
    bounded RufloCandidateBridge.
    """

    _hard_constraints = (
        "Ruflo output is validation-only guidance; no Codex execution is authorized.",
        "Network access and privileged execution are prohibited.",
        "MCP registration and Codex/Ruflo plugin installation are prohibited.",
        "Only the DAP-listed repository paths are in scope.",
    )

    def build(
        self,
        *,
        task: TaskLedgerRecord,
        admission: ExecutiveExecutionResponse,
        scope: RufloHandoffScope,
    ) -> RufloExecutiveHandoff:
        self._validate_source(task=task, admission=admission)

        constraints = list(
            dict.fromkeys([*scope.constraints, *self._hard_constraints])
        )
        request = RufloAdapterRequest(
            request_id=self._request_id(
                task=task,
                admission=admission,
                scope=scope,
            ),
            task=EngineeringTaskEnvelope(
                task_id=task.task_id,
                objective=task.objective,
                acceptance_criteria=list(scope.acceptance_criteria),
                allowed_paths=list(scope.allowed_paths),
                constraints=constraints,
                requires_network=False,
                requires_privileged_execution=False,
            ),
        )

        return RufloExecutiveHandoff(
            source_execution_id=admission.execution_id,
            source_delegation_id=admission.delegation_id,
            source_parent_task_id=admission.parent_task_id,
            source_task_id=task.task_id,
            source_task_sha256=self._model_hash(task),
            source_admission_sha256=self._model_hash(admission),
            request=request,
        )

    @staticmethod
    def _validate_source(
        *,
        task: TaskLedgerRecord,
        admission: ExecutiveExecutionResponse,
    ) -> None:
        if admission.disposition not in {"validated", "idempotent_replay"}:
            raise ValueError("execution admission is not validated")
        if admission.state != "validated" or not admission.admission_validated:
            raise ValueError("execution admission lacks validated DAP authority")
        if not admission.validation_only:
            raise ValueError("Ruflo handoff requires validation-only admission")

        side_effects = {
            "task_ledger_mutated": admission.task_ledger_mutated,
            "reservation_acquired": admission.reservation_acquired,
            "execution_started": admission.execution_started,
            "broker_activated": admission.broker_activated,
            "reservation_ids": bool(admission.reservation_ids),
        }
        enabled = [name for name, value in side_effects.items() if value]
        if enabled:
            raise ValueError(
                "execution admission already contains prohibited side effects: "
                + ", ".join(enabled)
            )

        if task.task_type != "agent":
            raise ValueError("only canonical child agent tasks may enter Ruflo")
        if task.status != "assigned":
            raise ValueError("Ruflo source task must remain assigned")
        if task.task_id not in admission.child_task_ids:
            raise ValueError("source task is not selected by the execution admission")
        if task.source_run_id != admission.delegation_id:
            raise ValueError("source task belongs to a different delegation")
        if task.parent_task_id != admission.parent_task_id:
            raise ValueError("source task belongs to a different parent task")
        if len(task.assigned_agent_ids) != 1:
            raise ValueError("source task must have exactly one assigned DAP agent")
        if task.assigned_agent_ids[0] not in admission.selected_agent_ids:
            raise ValueError("source task agent is not admitted by Executive Office")

    @classmethod
    def _request_id(
        cls,
        *,
        task: TaskLedgerRecord,
        admission: ExecutiveExecutionResponse,
        scope: RufloHandoffScope,
    ) -> str:
        canonical = json.dumps(
            {
                "execution_id": admission.execution_id,
                "task_id": task.task_id,
                "task_sha256": cls._model_hash(task),
                "admission_sha256": cls._model_hash(admission),
                "scope": scope.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()[:24]
        return f"ruflo-handoff-{digest}"

    @staticmethod
    def _model_hash(model: BaseModel) -> str:
        canonical = json.dumps(
            model.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


ruflo_executive_handoff_service = RufloExecutiveHandoffService()
