from fastapi import APIRouter, HTTPException, Query

from company.catalog import company_registry
from company.schemas import (
    DepartmentDefinition,
    DepartmentListResponse,
    DepartmentStatus,
    EmploymentStatus,
    OrganizationSnapshot,
    ReportingChainResponse,
    RoleDefinition,
    RoleKind,
    RoleListResponse,
)


router = APIRouter(
    prefix="/api/v1/company",
    tags=["DAP Company Registry"],
)


@router.get(
    "/organization",
    response_model=OrganizationSnapshot,
)
async def get_organization() -> OrganizationSnapshot:
    return company_registry.snapshot()


@router.get(
    "/departments",
    response_model=DepartmentListResponse,
)
async def list_departments(
    status: DepartmentStatus | None = None,
) -> DepartmentListResponse:
    return company_registry.list_departments(status=status)


@router.get(
    "/departments/{department_id}",
    response_model=DepartmentDefinition,
)
async def get_department(
    department_id: str,
) -> DepartmentDefinition:
    try:
        return company_registry.get_department(department_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@router.get(
    "/roles",
    response_model=RoleListResponse,
)
async def list_roles(
    department_id: str | None = None,
    status: EmploymentStatus | None = None,
    role_kind: RoleKind | None = None,
) -> RoleListResponse:
    try:
        return company_registry.list_roles(
            department_id=department_id,
            status=status,
            role_kind=role_kind,
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@router.get(
    "/roles/{role_id}/reporting-chain",
    response_model=ReportingChainResponse,
)
async def get_reporting_chain(
    role_id: str,
) -> ReportingChainResponse:
    try:
        return company_registry.reporting_chain(role_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@router.get(
    "/roles/{role_id}/direct-reports",
    response_model=RoleListResponse,
)
async def get_direct_reports(
    role_id: str,
) -> RoleListResponse:
    try:
        return company_registry.direct_reports(role_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@router.get(
    "/roles/{role_id}",
    response_model=RoleDefinition,
)
async def get_role(
    role_id: str,
) -> RoleDefinition:
    try:
        return company_registry.get_role(role_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
