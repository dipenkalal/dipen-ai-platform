from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from engineering.engineering_agent_service import ENGINEERING_AGENT_ID
from engineering.engineering_audit_evidence import EngineeringAuditEvidence

EngineeringWorkspaceState = Literal["queued", "active", "completed", "failed"]
EngineeringProvenanceState = Literal[
    "evidence_unavailable",
    "consistent",
    "requires_reconciliation",
]


class EngineeringWorkspaceEvidenceRecord(BaseModel):
    """Immutable evidence projection read from the Phase 11F audit table."""

    model_config = ConfigDict(frozen=True)

    evidence: EngineeringAuditEvidence
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stored_at: datetime


class EngineeringWorkspaceItem(BaseModel):
    """Read-only owner view over canonical task truth plus engineering evidence."""

    model_config = ConfigDict(frozen=True)

    task: TaskLedgerRecord
    workspace_state: EngineeringWorkspaceState
    provenance_state: EngineeringProvenanceState
    work_order_id: str | None = None
    evidence_count: int = Field(ge=0)
    latest_evidence: EngineeringWorkspaceEvidenceRecord | None = None
    owner_review_required: Literal[True] = True
    ui_execution_authority: Literal[False] = False
    ui_guardian_authority: Literal[False] = False
    ui_merge_authority: Literal[False] = False
    ui_deployment_authority: Literal[False] = False


class EngineeringWorkspaceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    queued: int = Field(ge=0)
    active: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    requires_reconciliation: int = Field(ge=0)


class EngineeringWorkspaceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: EngineeringWorkspaceSummary
    items: tuple[EngineeringWorkspaceItem, ...]
    read_only: Literal[True] = True
    execution_controls_exposed: Literal[False] = False


class EngineeringWorkspaceService:
    """Project Engineering Agent state without creating a second authority store."""

    def __init__(self, truth_repository: AgentTruthRepository) -> None:
        self.truth_repository = truth_repository

    def list_workspace(self) -> EngineeringWorkspaceResponse:
        tasks, _ = self.truth_repository.list_tasks(limit=500, offset=0)
        engineering_tasks = [
            task
            for task in tasks
            if task.task_type == "agent"
            and ENGINEERING_AGENT_ID in task.assigned_agent_ids
        ]
        evidence_by_task = self._read_evidence_by_task()
        items = tuple(
            self._project_item(
                task=task,
                evidence_records=evidence_by_task.get(task.task_id, []),
            )
            for task in engineering_tasks
        )
        return EngineeringWorkspaceResponse(
            summary=self._summary(items),
            items=items,
        )

    def get_item(self, task_id: str) -> EngineeringWorkspaceItem:
        task = self.truth_repository.get_task(task_id)
        if (
            task is None
            or task.task_type != "agent"
            or ENGINEERING_AGENT_ID not in task.assigned_agent_ids
        ):
            raise KeyError(f"Engineering task not found: {task_id}")
        evidence_records = self._read_evidence_by_task().get(task_id, [])
        return self._project_item(
            task=task,
            evidence_records=evidence_records,
        )

    def _read_evidence_by_task(
        self,
    ) -> dict[str, list[EngineeringWorkspaceEvidenceRecord]]:
        with self.truth_repository.connection() as connection:
            table = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'engineering_audit_evidence'
                """
            ).fetchone()
            if table is None:
                return {}

            rows = connection.execute(
                """
                SELECT evidence_sha256, source_task_id, evidence_json, stored_at
                FROM engineering_audit_evidence
                ORDER BY stored_at ASC, evidence_id ASC
                """
            ).fetchall()

        grouped: dict[str, list[EngineeringWorkspaceEvidenceRecord]] = defaultdict(list)
        for row in rows:
            grouped[str(row["source_task_id"])].append(
                EngineeringWorkspaceEvidenceRecord(
                    evidence=EngineeringAuditEvidence.model_validate_json(
                        str(row["evidence_json"])
                    ),
                    evidence_sha256=str(row["evidence_sha256"]),
                    stored_at=datetime.fromisoformat(str(row["stored_at"])),
                )
            )
        return dict(grouped)

    @classmethod
    def _project_item(
        cls,
        *,
        task: TaskLedgerRecord,
        evidence_records: list[EngineeringWorkspaceEvidenceRecord],
    ) -> EngineeringWorkspaceItem:
        latest = evidence_records[-1] if evidence_records else None
        return EngineeringWorkspaceItem(
            task=task,
            workspace_state=cls._workspace_state(task),
            provenance_state=cls._provenance_state(task=task, latest=latest),
            work_order_id=(latest.evidence.work_order_id if latest else None),
            evidence_count=len(evidence_records),
            latest_evidence=latest,
        )

    @staticmethod
    def _workspace_state(task: TaskLedgerRecord) -> EngineeringWorkspaceState:
        if task.status in {"running", "waiting"}:
            return "active"
        if task.status == "completed":
            return "completed"
        if task.status in {"failed", "cancelled", "manual_review"}:
            return "failed"
        return "queued"

    @staticmethod
    def _provenance_state(
        *,
        task: TaskLedgerRecord,
        latest: EngineeringWorkspaceEvidenceRecord | None,
    ) -> EngineeringProvenanceState:
        if latest is None:
            return "evidence_unavailable"

        outcome = latest.evidence.outcome
        if task.status == "completed":
            return "consistent" if outcome == "succeeded" else "requires_reconciliation"
        if task.status in {"failed", "cancelled", "manual_review"}:
            return (
                "consistent"
                if outcome in {"failed", "rejected", "cancelled"}
                else "requires_reconciliation"
            )
        return "requires_reconciliation"

    @staticmethod
    def _summary(
        items: tuple[EngineeringWorkspaceItem, ...],
    ) -> EngineeringWorkspaceSummary:
        return EngineeringWorkspaceSummary(
            total=len(items),
            queued=sum(item.workspace_state == "queued" for item in items),
            active=sum(item.workspace_state == "active" for item in items),
            completed=sum(item.workspace_state == "completed" for item in items),
            failed=sum(item.workspace_state == "failed" for item in items),
            requires_reconciliation=sum(
                item.provenance_state == "requires_reconciliation" for item in items
            ),
        )
