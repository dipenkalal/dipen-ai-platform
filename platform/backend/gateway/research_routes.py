from fastapi import APIRouter, HTTPException, Query

from agents.truth_repository import agent_truth_repository
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


research_workspace_service = ResearchWorkspaceService(
    retrieval_repository=ResearchRetrievalRepository(
        agent_truth_repository,
        initialize=False,
    ),
    run_repository=agent_run_repository,
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
