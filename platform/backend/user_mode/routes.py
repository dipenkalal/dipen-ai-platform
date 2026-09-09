from __future__ import annotations

import sqlite3

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from user_mode.config import (
    SESSION_ABSOLUTE_DAYS,
    SESSION_COOKIE_NAME,
    user_mode_db_path,
)
from user_mode.schemas import (
    LoginRequest,
    LoginResponse,
    SessionResponse,
    UserIdentity,
)
from user_mode.service import (
    AuthenticationError,
    UserModeService,
)


router = APIRouter(
    prefix="/api/v1/user",
    tags=["User Mode"],
)


def get_user_mode_service(
) -> UserModeService:
    return UserModeService(
        user_mode_db_path()
    )


def _user_identity(
    user: dict[str, object],
) -> UserIdentity:
    return UserIdentity(
        user_id=str(
            user["user_id"]
        ),
        email=str(
            user["email_normalized"]
        ),
        display_name=str(
            user["display_name"]
        ),
        role=str(
            user["role"]
        ),
    )


def _service_unavailable(
    exc: Exception,
) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="User Mode is unavailable",
    )


@router.post(
    "/auth/login",
    response_model=LoginResponse,
)
def login(
    body: LoginRequest,
    response: Response,
    service: UserModeService = Depends(
        get_user_mode_service
    ),
) -> LoginResponse:
    try:
        result = service.login(
            email=body.email,
            password=body.password,
        )

    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc

    except (
        sqlite3.OperationalError,
        FileNotFoundError,
    ) as exc:
        raise _service_unavailable(
            exc
        ) from exc

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=result.session_token,
        max_age=(
            SESSION_ABSOLUTE_DAYS
            * 24
            * 60
            * 60
        ),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    return LoginResponse(
        user=_user_identity(
            result.user
        )
    )


@router.get(
    "/auth/session",
    response_model=SessionResponse,
)
def session(
    request: Request,
    service: UserModeService = Depends(
        get_user_mode_service
    ),
) -> SessionResponse:
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    try:
        user = (
            service
            .authenticate_session(
                token or ""
            )
        )

    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        ) from exc

    except (
        sqlite3.OperationalError,
        FileNotFoundError,
    ) as exc:
        raise _service_unavailable(
            exc
        ) from exc

    return SessionResponse(
        user=_user_identity(
            user
        )
    )


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    service: UserModeService = Depends(
        get_user_mode_service
    ),
) -> Response:
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    try:
        service.logout(
            token
        )

    except (
        sqlite3.OperationalError,
        FileNotFoundError,
    ) as exc:
        raise _service_unavailable(
            exc
        ) from exc

    response = Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    return response
