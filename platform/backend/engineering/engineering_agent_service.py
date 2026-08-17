from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agents.truth_schemas import TaskLedgerRecord
from executive_office.schemas import ExecutiveExecutionResponse

ENGINEERING_AGENT_ID: Literal["engineering-agent"] = "engineering-agent"

PROTECTED_REPOSITORY_PREFIXES = (
    ".git/",
    ".github/workflows/",
    "platform/guardian/",
    "platform/backend/guardian/",
    "deploy/systemd/",
)
PROTECTED_REPOSITORY_EXACT_PATHS = frozenset(
    {
        ".git",
        ".github/workflows",
        "platform/guardian",
        "platform/backend/guardian",
        "deploy/systemd",
    }
)


class EngineeringWorkScope(BaseModel):
    """DAP-owned repository scope for a future Engineering Agent run."""

    acceptance_criteria: list[str] = Field(min_length=1, max_length=20)
    allowed_paths: list[str] = Field(min_length=1, max_length=40)
    constraints: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("acceptance_criteria", "constraints")
    @classmethod
    def normalize_text_items(cls, items: list[str]) -> list[str]:
        normalized = [item.strip() for item in items]
        if any(not item for item in normalized):
            raise ValueError("engineering scope text items must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("engineering scope text items must be unique")
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
                    "engineering paths must be repository-relative POSIX paths"
                )

            segments = value.split("/")
            if any(segment in {"", ".", ".."} for segment in segments):
                raise ValueError(
                    "engineering paths cannot contain empty, dot, or parent segments"
                )

            canonical = str(PurePosixPath(value))
            if canonical in PROTECTED_REPOSITORY_EXACT_PATHS or canonical.startswith(
                PROTECTED_REPOSITORY_PREFIXES
            ):
                raise ValueError(
                    f"engineering path is protected from autonomous mutation: {canonical}"
                )
            if canonical in seen:
                raise ValueError("engineering paths must be unique")
            seen.add(canonical)
            normalized.append(canonical)

        return normalized


class EngineeringWorkOrder(BaseModel):
    """Immutable, non-executing work order owned by DAP."""

    model_config = ConfigDict(frozen=True)

    work_order_id: str = Field(min_length=8, max_length=160)
    source_execution_id: str
    source_delegation_id: str
    source_parent_task_id: str
    source_task_id: str
    source_task_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assigned_agent_id: Literal["engineering-agent"] = ENGINEERING_AGENT_ID
    objective: str = Field(min_length=4, max_length=4000)
    acceptance_criteria: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    validation_only: Literal[True] = True
    owner_review_required: Literal[True] = True
    execution_authority_granted: Literal[False] = False
    repository_mutation_allowed: Literal[False] = False
    git_write_allowed: Literal[False] = False
    codex_execution_allowed: Literal[False] = False
    network_access_allowed: Literal[False] = False
    privileged_access_allowed: Literal[False] = False
    main_merge_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False

    def canonical_hash(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class EngineeringAgentService:
    """Prepare bounded Engineering Agent work without starting execution."""

    _hard_constraints = (
        "Engineering work remains non-executing until the Phase 11C executor admits it.",
        "Only DAP-listed repository paths are in scope.",
        "Network and privileged host access are prohibited by default.",
        "Main merge, release, deployment, Guardian mutation, and CI workflow mutation are prohibited.",
        "Owner review is required before any delivered change can advance beyond a draft review state.",
    )

    def prepare(
        self,
        *,
        task: TaskLedgerRecord,
        admission: ExecutiveExecutionResponse,
        scope: EngineeringWorkScope,
    ) -> EngineeringWorkOrder:
        self._validate_source(task=task, admission=admission)
        constraints = tuple(
            dict.fromkeys([*scope.constraints, *self._hard_constraints])
        )
        task_sha256 = self._model_hash(task)
        admission_sha256 = self._model_hash(admission)

        work_order_id = self._work_order_id(
            task=task,
            admission=admission,
            task_sha256=task_sha256,
            admission_sha256=admission_sha256,
            scope=scope,
        )

        return EngineeringWorkOrder(
            work_order_id=work_order_id,
            source_execution_id=admission.execution_id,
            source_delegation_id=admission.delegation_id,
            source_parent_task_id=admission.parent_task_id,
            source_task_id=task.task_id,
            source_task_sha256=task_sha256,
            source_admission_sha256=admission_sha256,
            objective=task.objective,
            acceptance_criteria=tuple(scope.acceptance_criteria),
            allowed_paths=tuple(scope.allowed_paths),
            constraints=constraints,
        )

    @staticmethod
    def _validate_source(
        *,
        task: TaskLedgerRecord,
        admission: ExecutiveExecutionResponse,
    ) -> None:
        if admission.disposition not in {"validated", "idempotent_replay"}:
            raise ValueError("engineering execution admission is not validated")
        if admission.state != "validated" or not admission.admission_validated:
            raise ValueError("engineering work lacks validated DAP admission")
        if not admission.validation_only:
            raise ValueError("Phase 11B requires validation-only admission")

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
                "engineering admission already contains prohibited side effects: "
                + ", ".join(enabled)
            )

        if task.task_type != "agent":
            raise ValueError("only canonical child agent tasks may become work orders")
        if task.status != "assigned":
            raise ValueError("engineering source task must remain assigned")
        if task.task_id not in admission.child_task_ids:
            raise ValueError("engineering source task is not selected by admission")
        if task.source_run_id != admission.delegation_id:
            raise ValueError("engineering source task belongs to another delegation")
        if task.parent_task_id != admission.parent_task_id:
            raise ValueError("engineering source task belongs to another parent task")
        if task.assigned_agent_ids != [ENGINEERING_AGENT_ID]:
            raise ValueError(
                "engineering source task must be assigned only to engineering-agent"
            )
        if ENGINEERING_AGENT_ID not in admission.selected_agent_ids:
            raise ValueError("engineering-agent is not selected by Executive Office")

    @classmethod
    def _work_order_id(
        cls,
        *,
        task: TaskLedgerRecord,
        admission: ExecutiveExecutionResponse,
        task_sha256: str,
        admission_sha256: str,
        scope: EngineeringWorkScope,
    ) -> str:
        encoded = json.dumps(
            {
                "task_id": task.task_id,
                "execution_id": admission.execution_id,
                "task_sha256": task_sha256,
                "admission_sha256": admission_sha256,
                "scope": scope.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()[:24]
        return f"engineering-work-{digest}"

    @staticmethod
    def _model_hash(model: BaseModel) -> str:
        encoded = json.dumps(
            model.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


engineering_agent_service = EngineeringAgentService()
