from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from career.dashboard import (
    CareerDashboardListResponse,
    CareerDashboardSummary,
    career_dashboard_service,
)
from career.http_schemas import (
    CareerAdvanceToReviewRequest,
    CareerApplicationEventListResponse,
    CareerApplicationMaterialListResponse,
    CareerApproveApplicationRequest,
    CareerCreateApplicationRequest,
    CareerCreateMaterialRequest,
    CareerCreateMaterialVersionRequest,
    CareerMarkMaterialReadyRequest,
    CareerMaterialDecisionRequest,
    CareerMaterialEventListResponse,
    CareerMaterialVersionListResponse,
    CareerTransitionRequest,
)
from career.http_support import (
    career_http_exception,
    get_career_domain_service,
)
from career.schemas import (
    CareerApplication,
    CareerApplicationMaterial,
    CareerApplicationMaterialEvent,
    CareerApplicationMaterialVersion,
    CareerApplicationReadiness,
    CareerOwnerReviewPackage,
    CareerOwnerReviewQueue,
)
from career.service import (
    CareerDomainService,
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


@router.get(
    "/applications/{application_id}",
    response_model=CareerApplication,
)
async def get_career_application(
    application_id: str,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplication:
    try:
        return service.get_cockpit_application(
            application_id=application_id
        )
    except Exception as error:
        raise career_http_exception(
            error
        ) from error


@router.get(
    "/applications/{application_id}/events",
    response_model=(
        CareerApplicationEventListResponse
    ),
)
async def list_career_application_events(
    application_id: str,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplicationEventListResponse:
    try:
        items = (
            service
            .list_cockpit_application_events(
                application_id=application_id
            )
        )

        return CareerApplicationEventListResponse(
            total=len(items),
            items=items,
        )
    except Exception as error:
        raise career_http_exception(
            error
        ) from error


@router.get(
    "/applications/{application_id}/readiness",
    response_model=CareerApplicationReadiness,
)
async def get_career_application_readiness(
    application_id: str,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplicationReadiness:
    try:
        return (
            service
            .get_cockpit_application_readiness(
                application_id=application_id
            )
        )
    except Exception as error:
        raise career_http_exception(
            error
        ) from error


@router.get(
    "/applications/{application_id}/materials",
    response_model=(
        CareerApplicationMaterialListResponse
    ),
)
async def list_career_application_materials(
    application_id: str,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplicationMaterialListResponse:
    try:
        items = (
            service
            .list_cockpit_application_materials(
                application_id=application_id
            )
        )

        return (
            CareerApplicationMaterialListResponse(
                total=len(items),
                items=items,
            )
        )
    except Exception as error:
        raise career_http_exception(
            error
        ) from error


@router.get(
    "/materials/{material_id}/versions",
    response_model=(
        CareerMaterialVersionListResponse
    ),
)
async def list_career_material_versions(
    material_id: str,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerMaterialVersionListResponse:
    try:
        items = (
            service
            .list_cockpit_material_versions(
                material_id=material_id
            )
        )

        return CareerMaterialVersionListResponse(
            total=len(items),
            items=items,
        )
    except Exception as error:
        raise career_http_exception(
            error
        ) from error


@router.get(
    "/material-versions/"
    "{material_version_id}/events",
    response_model=(
        CareerMaterialEventListResponse
    ),
)
async def list_career_material_events(
    material_version_id: str,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerMaterialEventListResponse:
    try:
        items = (
            service
            .list_cockpit_material_events(
                material_version_id=(
                    material_version_id
                )
            )
        )

        return CareerMaterialEventListResponse(
            total=len(items),
            items=items,
        )
    except Exception as error:
        raise career_http_exception(
            error
        ) from error



@router.get(
    "/owner-review/queue",
    response_model=CareerOwnerReviewQueue,
)
async def list_career_owner_review_queue(
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerOwnerReviewQueue:
    try:
        return service.list_owner_review_queue()
    except Exception as error:
        raise career_http_exception(
            error
        ) from error


@router.get(
    "/applications/{application_id}/owner-review",
    response_model=CareerOwnerReviewPackage,
)
async def get_career_owner_review_package(
    application_id: str,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerOwnerReviewPackage:
    try:
        return service.get_owner_review_package(
            application_id=application_id
        )
    except Exception as error:
        raise career_http_exception(
            error
        ) from error


def _career_http_now(
) -> datetime:
    return datetime.now(timezone.utc)


@router.post(
    "/jobs/{job_id}/application",
    response_model=CareerApplication,
)
async def create_career_application(
    job_id: str,
    request: CareerCreateApplicationRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplication:
    try:
        return service.create_cockpit_application(
            job_id=job_id,
            reason=request.reason,
            notes=request.notes,
            occurred_at=_career_http_now(),
        )
    except Exception as error:
        raise career_http_exception(error) from error


@router.post(
    "/applications/{application_id}/transitions",
    response_model=CareerApplication,
)
async def transition_career_application(
    application_id: str,
    request: CareerTransitionRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplication:
    guarded_targets = {
        "READY_FOR_REVIEW",
        "OWNER_APPROVED",
        "APPLIED_CONFIRMED",
    }

    if request.to_state in guarded_targets:
        raise HTTPException(
            status_code=403,
            detail=(
                "This Career transition requires "
                "a dedicated guarded operation."
            ),
        )

    try:
        return service.transition_application(
            application_id=application_id,
            to_state=request.to_state,
            actor_kind="OWNER",
            actor_id="dipen-owner",
            reason=request.reason,
            evidence_id=request.evidence_id,
            occurred_at=_career_http_now(),
        )
    except Exception as error:
        raise career_http_exception(error) from error


@router.post(
    "/applications/{application_id}/advance-to-review",
    response_model=CareerApplication,
)
async def advance_career_application_to_review(
    application_id: str,
    request: CareerAdvanceToReviewRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplication:
    try:
        return (
            service
            .advance_preparing_application_to_review(
                application_id=application_id,
                reason=request.reason,
                occurred_at=_career_http_now(),
            )
        )
    except Exception as error:
        raise career_http_exception(error) from error


@router.post(
    "/applications/{application_id}/approve",
    response_model=CareerApplication,
)
async def approve_career_application(
    application_id: str,
    request: CareerApproveApplicationRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplication:
    try:
        return service.approve_ready_application(
            application_id=application_id,
            reason=request.reason,
            occurred_at=_career_http_now(),
        )
    except Exception as error:
        raise career_http_exception(error) from error


@router.post(
    "/applications/{application_id}/materials",
    response_model=CareerApplicationMaterial,
)
async def create_career_application_material(
    application_id: str,
    request: CareerCreateMaterialRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplicationMaterial:
    try:
        return service.create_material(
            application_id=application_id,
            material_kind=request.material_kind,
            label=request.label,
            created_at=_career_http_now(),
        )
    except Exception as error:
        raise career_http_exception(error) from error


@router.post(
    "/materials/{material_id}/versions",
    response_model=CareerApplicationMaterialVersion,
)
async def create_career_material_version(
    material_id: str,
    request: CareerCreateMaterialVersionRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplicationMaterialVersion:
    try:
        return (
            service
            .create_cockpit_material_version(
                material_id=material_id,
                source_snapshot_id=(
                    request.source_snapshot_id
                ),
                content_format=(
                    request.content_format
                ),
                content_text=request.content_text,
                parent_material_version_id=(
                    request
                    .parent_material_version_id
                ),
                profile_version=(
                    request.profile_version
                ),
                occurred_at=_career_http_now(),
            )
        )
    except Exception as error:
        raise career_http_exception(error) from error


@router.post(
    "/material-versions/{material_version_id}/ready",
    response_model=CareerApplicationMaterialEvent,
)
async def mark_career_material_version_ready(
    material_version_id: str,
    request: CareerMarkMaterialReadyRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplicationMaterialEvent:
    try:
        return service.mark_material_version_ready(
            material_version_id=(
                material_version_id
            ),
            actor_kind="OWNER",
            actor_id="dipen-owner",
            reason=request.reason,
            occurred_at=_career_http_now(),
        )
    except Exception as error:
        raise career_http_exception(error) from error


@router.post(
    "/material-versions/{material_version_id}/decision",
    response_model=CareerApplicationMaterialEvent,
)
async def decide_career_material_version(
    material_version_id: str,
    request: CareerMaterialDecisionRequest,
    service: CareerDomainService = Depends(
        get_career_domain_service
    ),
) -> CareerApplicationMaterialEvent:
    try:
        if request.decision == "approve":
            reason = (
                request.reason
                or "Owner approved material version."
            )

            return service.approve_material_version(
                material_version_id=(
                    material_version_id
                ),
                owner_id="dipen-owner",
                reason=reason,
                occurred_at=_career_http_now(),
            )

        return service.reject_material_version(
            material_version_id=(
                material_version_id
            ),
            owner_id="dipen-owner",
            reason=request.reason,
            occurred_at=_career_http_now(),
        )
    except Exception as error:
        raise career_http_exception(error) from error
