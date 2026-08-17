from fastapi import APIRouter, HTTPException

from agents.truth_repository import agent_truth_repository
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
