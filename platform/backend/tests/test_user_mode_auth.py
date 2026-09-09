from __future__ import annotations

import sqlite3
from datetime import (
    UTC,
    datetime,
)
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import (
    TestClient,
)

from user_mode.config import (
    DEFAULT_USER_MODE_DB_PATH,
    SESSION_COOKIE_NAME,
)
from user_mode.database import (
    initialize_database,
)
from user_mode.repository import (
    AccountLimitError,
    AdminLimitError,
    DuplicateUserError,
)
from user_mode.routes import (
    get_user_mode_service,
    router,
)
from user_mode.security import (
    hash_session_token,
)
from user_mode.service import (
    AuthenticationError,
    UserModeService,
)


PASSWORD = "DAP-v22-Test-Passphrase!"


@pytest.fixture
def db_path(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path
        / "user-mode-test.db"
    )

    initialize_database(
        path
    )

    return path


@pytest.fixture
def service(
    db_path: Path,
) -> UserModeService:
    return UserModeService(
        db_path
    )


@pytest.fixture
def client(
    service: UserModeService,
):
    app = FastAPI()

    app.include_router(
        router
    )

    app.dependency_overrides[
        get_user_mode_service
    ] = lambda: service

    with TestClient(
        app,
        base_url="https://testserver",
    ) as test_client:
        yield test_client


def create_user(
    service: UserModeService,
    *,
    email: str = "user@example.com",
    role: str = "user",
):
    return service.create_user(
        email=email,
        display_name="Test User",
        password=PASSWORD,
        role=role,
    )


def session_token_from(
    response,
) -> str:
    token = response.cookies.get(
        SESSION_COOKIE_NAME
    )

    assert token
    return token


def test_password_is_argon2id_and_raw_absent(
    service: UserModeService,
    db_path: Path,
):
    create_user(service)

    connection = sqlite3.connect(
        db_path
    )

    try:
        row = connection.execute(
            """
            SELECT
                email_normalized,
                display_name,
                password_hash
            FROM users
            """
        ).fetchone()

    finally:
        connection.close()

    assert row is not None

    password_hash = row[2]

    assert password_hash.startswith(
        "$argon2id$"
    )

    assert PASSWORD not in (
        "|".join(
            str(value)
            for value in row
        )
    )


def test_normalized_email_uniqueness(
    service: UserModeService,
):
    create_user(
        service,
        email="Person@Example.COM",
    )

    with pytest.raises(
        DuplicateUserError
    ):
        create_user(
            service,
            email=" person@example.com ",
        )


def test_unknown_and_bad_password_are_generic(
    service: UserModeService,
    client: TestClient,
):
    create_user(service)

    unknown = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "unknown@example.com",
            "password": PASSWORD,
        },
    )

    incorrect = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "user@example.com",
            "password": "Wrong-Password-123!",
        },
    )

    assert unknown.status_code == 401
    assert incorrect.status_code == 401

    assert unknown.json() == (
        incorrect.json()
    )

    assert unknown.json() == {
        "detail": (
            "Invalid email or password"
        )
    }


def test_inactive_user_is_rejected(
    service: UserModeService,
    client: TestClient,
):
    user = create_user(service)

    service.repository.set_user_active(
        user_id=str(
            user["user_id"]
        ),
        is_active=False,
        updated_at=(
            datetime.now(UTC)
            .isoformat()
        ),
    )

    response = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "user@example.com",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Invalid email or password"
        )
    }


def test_valid_login_creates_hashed_session(
    service: UserModeService,
    client: TestClient,
    db_path: Path,
):
    create_user(service)

    response = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "USER@example.com",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200

    token = session_token_from(
        response
    )

    connection = sqlite3.connect(
        db_path
    )

    try:
        row = connection.execute(
            """
            SELECT token_hash
            FROM sessions
            """
        ).fetchone()

    finally:
        connection.close()

    assert row is not None

    stored_hash = row[0]

    assert stored_hash != token

    assert stored_hash == (
        hash_session_token(
            token
        )
    )


def test_login_cookie_security_flags(
    service: UserModeService,
    client: TestClient,
):
    create_user(service)

    response = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "user@example.com",
            "password": PASSWORD,
        },
    )

    cookie = response.headers[
        "set-cookie"
    ]

    lowered = cookie.lower()

    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=lax" in lowered
    assert "path=/" in lowered


def test_login_client_cannot_supply_role(
    service: UserModeService,
    client: TestClient,
):
    create_user(service)

    response = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "user@example.com",
            "password": PASSWORD,
            "role": "admin",
        },
    )

    assert response.status_code == 422


def test_session_lookup_works(
    service: UserModeService,
    client: TestClient,
):
    user = create_user(service)

    login = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "user@example.com",
            "password": PASSWORD,
        },
    )

    assert login.status_code == 200

    response = client.get(
        "/api/v1/user/auth/session"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["authenticated"] is True

    assert (
        body["user"]["user_id"]
        == user["user_id"]
    )

    assert (
        body["user"]["role"]
        == "user"
    )


def test_idle_expiry_fails_closed(
    service: UserModeService,
    db_path: Path,
):
    create_user(service)

    result = service.login(
        email="user@example.com",
        password=PASSWORD,
    )

    connection = sqlite3.connect(
        db_path
    )

    try:
        connection.execute(
            """
            UPDATE sessions
            SET idle_expires_at =
                '2000-01-01T00:00:00+00:00'
            """
        )

        connection.commit()

    finally:
        connection.close()

    with pytest.raises(
        AuthenticationError
    ):
        service.authenticate_session(
            result.session_token
        )


def test_absolute_expiry_fails_closed(
    service: UserModeService,
    db_path: Path,
):
    create_user(service)

    result = service.login(
        email="user@example.com",
        password=PASSWORD,
    )

    connection = sqlite3.connect(
        db_path
    )

    try:
        connection.execute(
            """
            UPDATE sessions
            SET absolute_expires_at =
                '2000-01-01T00:00:00+00:00'
            """
        )

        connection.commit()

    finally:
        connection.close()

    with pytest.raises(
        AuthenticationError
    ):
        service.authenticate_session(
            result.session_token
        )


def test_revoked_session_fails_closed(
    service: UserModeService,
):
    create_user(service)

    result = service.login(
        email="user@example.com",
        password=PASSWORD,
    )

    service.logout(
        result.session_token
    )

    with pytest.raises(
        AuthenticationError
    ):
        service.authenticate_session(
            result.session_token
        )


def test_logout_route_revokes_session(
    service: UserModeService,
    client: TestClient,
):
    create_user(service)

    login = client.post(
        "/api/v1/user/auth/login",
        json={
            "email": "user@example.com",
            "password": PASSWORD,
        },
    )

    assert login.status_code == 200

    logout = client.post(
        "/api/v1/user/auth/logout"
    )

    assert logout.status_code == 204

    session = client.get(
        "/api/v1/user/auth/session"
    )

    assert session.status_code == 401


def test_second_admin_is_rejected(
    service: UserModeService,
):
    create_user(
        service,
        email="admin1@example.com",
        role="admin",
    )

    with pytest.raises(
        AdminLimitError
    ):
        create_user(
            service,
            email="admin2@example.com",
            role="admin",
        )


def test_third_total_account_is_rejected(
    service: UserModeService,
):
    create_user(
        service,
        email="first@example.com",
        role="admin",
    )

    create_user(
        service,
        email="second@example.com",
        role="user",
    )

    with pytest.raises(
        AccountLimitError
    ):
        create_user(
            service,
            email="third@example.com",
            role="user",
        )


def test_database_is_temporary(
    db_path: Path,
    tmp_path: Path,
):
    assert db_path.is_file()

    assert db_path.parent == tmp_path

    assert (
        db_path
        != DEFAULT_USER_MODE_DB_PATH
    )


def test_production_database_remains_absent():
    assert not (
        DEFAULT_USER_MODE_DB_PATH.exists()
    )
