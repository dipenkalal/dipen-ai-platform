from fastapi import APIRouter, HTTPException

from agents.truth_repository import agent_truth_repository
from engineering.engineering_audit_repository import EngineeringAuditRepository
from engineering.engineering_owner_review import (
    EngineeringOwnerReviewDecisionRequest,
    EngineeringOwnerReviewListResponse,
    EngineeringOwnerReviewView,
    engineering_owner_review_service,
)
from engineering.engineering_owner_review_repository import (
    EngineeringOwnerReviewConflict,
    EngineeringOwnerReviewRepository,
)
from engineering.engineering_workspace import (
    EngineeringWorkspaceItem,
    EngineeringWorkspaceResponse,
    EngineeringWorkspaceService,
)

router = APIRouter(
    prefix="/api/v1/engineering",
    tags=["Engineering Workspace"],
)

workspace_service = EngineeringWorkspaceService(agent_truth_repository)
audit_repository = EngineeringAuditRepository(agent_truth_repository)
owner_review_repository = EngineeringOwnerReviewRepository(
    agent_truth_repository,
    audit_repository,
)


@router.get(
    "/workspace",
    response_model=EngineeringWorkspaceResponse,
)
async def list_engineering_workspace() -> EngineeringWorkspaceResponse:
    return workspace_service.list_workspace()


@router.get(
    "/workspace/{task_id}",
    response_model=EngineeringWorkspaceItem,
)
async def get_engineering_workspace_item(
    task_id: str,
) -> EngineeringWorkspaceItem:
    try:
        return workspace_service.get_item(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get(
    "/reviews",
    response_model=EngineeringOwnerReviewListResponse,
)
async def list_engineering_owner_reviews() -> EngineeringOwnerReviewListResponse:
    views: list[EngineeringOwnerReviewView] = []
    for record in audit_repository.list_recent(limit=200):
        if record.evidence.outcome != "succeeded":
            continue
        task = agent_truth_repository.get_task(record.evidence.source_task_id)
        if task is None:
            continue
        package = engineering_owner_review_service.build_package(task=task, record=record)
        persisted = owner_review_repository.get_for_evidence(record.evidence.evidence_id)
        views.append(
            EngineeringOwnerReviewView(
                package=package,
                decision=persisted.decision if persisted is not None else None,
            )
        )

    pending = sum(view.decision is None for view in views)
    approved = sum(
        view.decision is not None and view.decision.decision == "approve"
        for view in views
    )
    rejected = sum(
        view.decision is not None and view.decision.decision == "reject"
        for view in views
    )
    return EngineeringOwnerReviewListResponse(
        reviews=tuple(views),
        review_count=len(views),
        pending_count=pending,
        approved_count=approved,
        rejected_count=rejected,
    )


@router.get(
    "/reviews/{evidence_id}",
    response_model=EngineeringOwnerReviewView,
)
async def get_engineering_owner_review(
    evidence_id: str,
) -> EngineeringOwnerReviewView:
    record = audit_repository.get(evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="engineering evidence was not found")
    task = agent_truth_repository.get_task(record.evidence.source_task_id)
    if task is None:
        raise HTTPException(status_code=409, detail="canonical engineering task is missing")
    try:
        package = engineering_owner_review_service.build_package(task=task, record=record)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    persisted = owner_review_repository.get_for_evidence(evidence_id)
    return EngineeringOwnerReviewView(
        package=package,
        decision=persisted.decision if persisted is not None else None,
    )


@router.post(
    "/reviews/{evidence_id}/decision",
    response_model=EngineeringOwnerReviewView,
)
async def decide_engineering_owner_review(
    evidence_id: str,
    request: EngineeringOwnerReviewDecisionRequest,
) -> EngineeringOwnerReviewView:
    record = audit_repository.get(evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="engineering evidence was not found")
    task = agent_truth_repository.get_task(record.evidence.source_task_id)
    if task is None:
        raise HTTPException(status_code=409, detail="canonical engineering task is missing")
    try:
        package = engineering_owner_review_service.build_package(task=task, record=record)
        decision = engineering_owner_review_service.decide(
            package=package,
            request=request,
        )
        persisted = owner_review_repository.persist(decision)
    except EngineeringOwnerReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return EngineeringOwnerReviewView(
        package=package,
        decision=persisted.decision,
    )
