from __future__ import annotations

import sqlite3
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from gateway.research_retrieval_evidence import ResearchRetrievalEvidence
from gateway.research_retrieval_repository import PersistedResearchRetrievalRecord
from history.schemas import AgentRunRecord, AgentRunSummary, HistoryRunStatus


class ResearchRetrievalReadRepository(Protocol):
    def get(self, evidence_id: str) -> PersistedResearchRetrievalRecord | None: ...

    def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> list[PersistedResearchRetrievalRecord]: ...


class AgentRunHistoryReadRepository(Protocol):
    def get(self, run_id: str) -> AgentRunRecord | None: ...

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        agent_id: str | None = None,
        status: str | None = None,
        model: str | None = None,
        search: str | None = None,
    ) -> tuple[list[AgentRunSummary], int]: ...


class ResearchWorkspaceRunContext(BaseModel):
    """Read-only agent-run context correlated to immutable retrieval evidence."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    agent_id: str
    objective: str
    status: HistoryRunStatus
    started_at: str
    completed_at: str
    provenance_source: Literal["agent_run_history"] = "agent_run_history"


class ResearchWorkspaceEvidenceItem(BaseModel):
    """Owner-facing read model; the underlying evidence remains unchanged."""

    model_config = ConfigDict(frozen=True)

    evidence: ResearchRetrievalEvidence
    stored_at: str
    run: ResearchWorkspaceRunContext | None = None
    provenance_kind: Literal["internet_evidence"] = "internet_evidence"
    provenance_label: Literal["Internet Evidence"] = "Internet Evidence"
    knowledge_record: Literal[False] = False
    search_candidate_metadata_included: Literal[False] = False
    ui_network_authority_granted: Literal[False] = False
    ui_mutation_authority_granted: Literal[False] = False


class ResearchWorkspaceListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[ResearchWorkspaceEvidenceItem]
    total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    workspace_mode: Literal["read_only"] = "read_only"
    network_authority_granted: Literal[False] = False
    mutation_authority_granted: Literal[False] = False
    search_candidate_metadata_included: Literal[False] = False


class ResearchWorkspaceService:
    """Project persisted internet evidence into a read-only owner workspace."""

    _RUN_SCAN_LIMIT = 500

    def __init__(
        self,
        *,
        retrieval_repository: ResearchRetrievalReadRepository,
        run_repository: AgentRunHistoryReadRepository,
    ) -> None:
        self._retrieval_repository = retrieval_repository
        self._run_repository = run_repository

    def list_evidence(self, *, limit: int = 100) -> ResearchWorkspaceListResponse:
        if limit < 1 or limit > 500:
            raise ValueError("research workspace list limit must be between 1 and 500")

        records = self._list_recent_or_empty(limit=limit)
        evidence_runs, request_runs = self._run_context_indexes(records)
        items = [
            self._item(
                record,
                evidence_runs=evidence_runs,
                request_runs=request_runs,
            )
            for record in records
        ]
        return ResearchWorkspaceListResponse(
            items=items,
            total=len(items),
            succeeded=sum(item.evidence.outcome == "succeeded" for item in items),
            failed=sum(item.evidence.outcome == "failed" for item in items),
            cancelled=sum(item.evidence.outcome == "cancelled" for item in items),
            limit=limit,
        )

    def get_evidence(self, evidence_id: str) -> ResearchWorkspaceEvidenceItem | None:
        try:
            record = self._retrieval_repository.get(evidence_id)
        except sqlite3.OperationalError as exc:
            if self._missing_retrieval_table(exc):
                return None
            raise
        if record is None:
            return None

        evidence_runs, request_runs = self._run_context_indexes([record])
        return self._item(
            record,
            evidence_runs=evidence_runs,
            request_runs=request_runs,
        )

    def _list_recent_or_empty(
        self,
        *,
        limit: int,
    ) -> list[PersistedResearchRetrievalRecord]:
        try:
            return self._retrieval_repository.list_recent(limit=limit)
        except sqlite3.OperationalError as exc:
            if self._missing_retrieval_table(exc):
                return []
            raise

    def _run_context_indexes(
        self,
        records: list[PersistedResearchRetrievalRecord],
    ) -> tuple[
        dict[str, ResearchWorkspaceRunContext],
        dict[str, ResearchWorkspaceRunContext],
    ]:
        if not records:
            return {}, {}

        wanted_evidence_ids = {record.evidence.evidence_id for record in records}
        wanted_request_ids = {record.evidence.request_id for record in records}
        evidence_runs: dict[str, ResearchWorkspaceRunContext] = {}
        request_runs: dict[str, ResearchWorkspaceRunContext] = {}

        summaries, _ = self._run_repository.list(
            limit=self._RUN_SCAN_LIMIT,
            offset=0,
            agent_id="research-agent",
        )
        for summary in summaries:
            if (
                wanted_evidence_ids.issubset(evidence_runs)
                and wanted_request_ids.issubset(request_runs)
            ):
                break
            record = self._run_repository.get(summary.run_id)
            if record is None:
                continue
            context = self._run_context(record)

            for source in record.sources:
                evidence_id = source.get("evidence_id")
                if isinstance(evidence_id, str) and evidence_id in wanted_evidence_ids:
                    evidence_runs.setdefault(evidence_id, context)

            for step in record.steps:
                if step.tool_id != "internet.research.retrieve":
                    continue
                output = step.output
                if not isinstance(output, dict):
                    continue
                request_id = output.get("request_id")
                if isinstance(request_id, str) and request_id in wanted_request_ids:
                    request_runs.setdefault(request_id, context)
                sources = output.get("sources")
                if not isinstance(sources, list):
                    continue
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    evidence_id = source.get("evidence_id")
                    if isinstance(evidence_id, str) and evidence_id in wanted_evidence_ids:
                        evidence_runs.setdefault(evidence_id, context)

        return evidence_runs, request_runs

    @staticmethod
    def _run_context(record: AgentRunRecord) -> ResearchWorkspaceRunContext:
        return ResearchWorkspaceRunContext(
            run_id=record.run_id,
            agent_id=record.agent_id,
            objective=record.objective,
            status=record.status,
            started_at=record.started_at.isoformat(),
            completed_at=record.completed_at.isoformat(),
        )

    @staticmethod
    def _item(
        record: PersistedResearchRetrievalRecord,
        *,
        evidence_runs: dict[str, ResearchWorkspaceRunContext],
        request_runs: dict[str, ResearchWorkspaceRunContext],
    ) -> ResearchWorkspaceEvidenceItem:
        evidence = record.evidence
        run = evidence_runs.get(evidence.evidence_id) or request_runs.get(
            evidence.request_id
        )
        return ResearchWorkspaceEvidenceItem(
            evidence=evidence,
            stored_at=record.stored_at.isoformat(),
            run=run,
        )

    @staticmethod
    def _missing_retrieval_table(error: sqlite3.OperationalError) -> bool:
        return "no such table: research_retrieval_evidence" in str(error).lower()
