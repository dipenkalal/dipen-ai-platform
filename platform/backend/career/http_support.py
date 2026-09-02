from __future__ import annotations

import sqlite3

from fastapi import HTTPException

from agents.truth_repository import (
    agent_truth_repository,
)
from career.repository import (
    CareerPersistenceConflict,
    CareerRepository,
)
from career.service import (
    CareerAdmissionRejected,
    CareerAuthorizationRejected,
    CareerDomainService,
    CareerMaterialRejected,
    CareerTransitionRejected,
)


def get_career_domain_service(
) -> CareerDomainService:
    repository = CareerRepository(
        agent_truth_repository,
        initialize=False,
    )

    return CareerDomainService(
        repository
    )


def career_http_exception(
    error: Exception,
) -> HTTPException:
    if isinstance(
        error,
        CareerAuthorizationRejected,
    ):
        return HTTPException(
            status_code=403,
            detail=str(error),
        )

    if isinstance(
        error,
        (
            CareerAdmissionRejected,
            CareerTransitionRejected,
            CareerMaterialRejected,
            CareerPersistenceConflict,
        ),
    ):
        return HTTPException(
            status_code=409,
            detail=str(error),
        )

    if isinstance(
        error,
        (KeyError,),
    ):
        return HTTPException(
            status_code=404,
            detail=str(error),
        )

    if isinstance(
        error,
        FileNotFoundError,
    ):
        return HTTPException(
            status_code=503,
            detail=str(error),
        )

    if isinstance(
        error,
        sqlite3.OperationalError,
    ):
        message = str(error)

        if "no such table" in message.lower():
            return HTTPException(
                status_code=503,
                detail=message,
            )

    return HTTPException(
        status_code=500,
        detail="Career Cockpit internal error.",
    )
