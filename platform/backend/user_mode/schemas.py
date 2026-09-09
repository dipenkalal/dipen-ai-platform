from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    model_config = {
        "extra": "forbid",
    }

    email: str = Field(
        min_length=3,
        max_length=320,
    )

    password: str = Field(
        min_length=8,
        max_length=1024,
    )


class UserIdentity(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: Literal[
        "user",
        "admin",
    ]


class LoginResponse(BaseModel):
    authenticated: Literal[True] = True
    user: UserIdentity


class SessionResponse(BaseModel):
    authenticated: Literal[True] = True
    user: UserIdentity
