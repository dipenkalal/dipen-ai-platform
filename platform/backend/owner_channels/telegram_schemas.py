from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool = False
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str


class TelegramMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: int
    date: int
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None


TelegramOwnerCommandName = Literal[
    "status",
    "agents",
    "tasks",
    "company",
    "cancel",
    "help",
    "unsupported",
]


class TelegramOwnerCommand(BaseModel):
    update_id: int
    message_id: int
    command: TelegramOwnerCommandName
    execution_id: str | None = None
    idempotency_key: str
    authorized_by: Literal["dipen-owner"] = "dipen-owner"
    accepted: bool
    reason: str
