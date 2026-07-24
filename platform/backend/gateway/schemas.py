from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None
    provider: Literal["auto", "ollama"] = "auto"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=512, ge=1, le=8192)
    stream: bool = False


class UsageMetrics(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float


class ChatResponse(BaseModel):
    provider: str
    model: str
    message: ChatMessage
    usage: UsageMetrics


class ModelInfo(BaseModel):
    provider: str
    id: str
    name: str
    local: bool
    available: bool
    size_bytes: int | None = None


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
