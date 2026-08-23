from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from career.dashboard import (
    CareerDashboardListResponse,
    CareerDashboardSummary,
    career_dashboard_service,
)


router = APIRouter(
    prefix="/api/v1/career",
    tags=["Career"],
)


@router.get(
    "/summary",
    response_model=CareerDashboardSummary,
)
async def get_career_summary(
) -> CareerDashboardSummary:
    try:
        return career_dashboard_service.summary()
    except (
        FileNotFoundError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@router.get(
    "/jobs",
    response_model=CareerDashboardListResponse,
)
async def list_career_jobs(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
) -> CareerDashboardListResponse:
    try:
        return career_dashboard_service.list_jobs(
            limit=limit
        )
    except (
        FileNotFoundError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
