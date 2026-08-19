from fastapi import APIRouter, HTTPException, Query

from agents.truth_repository import agent_truth_repository
from gateway.research_operations import (
    ResearchOperationsService,
    ResearchOperationsSummary,
    ResearchRetentionPlan,
)
from gateway.research_operations_repository import ResearchOperationsRepository
from gateway.research_provider_health import (
    ResearchProviderHealth,
    check_searxng_health,
)
from gateway.research_provider_readiness import (
    ResearchProviderReadiness,
    assess_phase15_provider_readiness,
    load_phase15_live_report,
)
from gateway.research_resource_snapshot import (
    ResearchResourceSnapshot,
    capture_research_resource_snapshot,
)
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.research_workspace import (
    ResearchWorkspaceEvidenceItem,
    ResearchWorkspaceListResponse,
    ResearchWorkspaceService,
)
from history.repository import agent_run_repository

router = APIRouter(
    prefix="/api/v1/research",
    tags=["Research Workspace"],
)


_retrieval_repository = ResearchRetrievalRepository(
    agent_truth_repository,
    initialize=False,
)

research_workspace_service = ResearchWorkspaceService(
    retrieval_repository=_retrieval_repository,
    run_repository=agent_run_repository,
)

research_operations_service = ResearchOperationsService(
    evidence_repository=_retrieval_repository,
    operations_repository=ResearchOperationsRepository(
        agent_truth_repository,
        initialize=False,
    ),
)


@router.get(
    "/evidence",
    response_model=ResearchWorkspaceListResponse,
)
async def list_research_evidence(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
) -> ResearchWorkspaceListResponse:
    return research_workspace_service.list_evidence(limit=limit)


@router.get(
    "/evidence/{evidence_id}",
    response_model=ResearchWorkspaceEvidenceItem,
)
async def get_research_evidence(
    evidence_id: str,
) -> ResearchWorkspaceEvidenceItem:
    item = research_workspace_service.get_evidence(evidence_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Research evidence was not found.",
        )
    return item


@router.get(
    "/operations",
    response_model=ResearchOperationsSummary,
)
async def get_research_operations(
    evidence_limit: int = Query(default=500, ge=1, le=500),
    event_limit: int = Query(default=2000, ge=1, le=2000),
) -> ResearchOperationsSummary:
    return research_operations_service.summary(
        evidence_limit=evidence_limit,
        event_limit=event_limit,
    )


@router.get(
    "/operations/provider-health",
    response_model=ResearchProviderHealth,
)
async def get_research_provider_health() -> ResearchProviderHealth:
    return await check_searxng_health()


@router.get(
    "/operations/provider-readiness",
    response_model=ResearchProviderReadiness,
)
async def get_research_provider_readiness() -> ResearchProviderReadiness:
    operations = research_operations_service.summary()
    health = await check_searxng_health()
    return assess_phase15_provider_readiness(
        operations=operations,
        health=health,
        loaded_report=load_phase15_live_report(),
    )


@router.get(
    "/operations/resource-snapshot",
    response_model=ResearchResourceSnapshot,
)
async def get_research_resource_snapshot() -> ResearchResourceSnapshot:
    return capture_research_resource_snapshot()


@router.get(
    "/operations/retention-plan",
    response_model=ResearchRetentionPlan,
)
async def get_research_retention_plan(
    evidence_limit: int = Query(default=500, ge=1, le=500),
) -> ResearchRetentionPlan:
    return research_operations_service.retention_plan(
        evidence_limit=evidence_limit,
    )
