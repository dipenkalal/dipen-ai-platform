from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.schemas import AgentRunRequest
from agents.service import agent_service


DAP_AUTO_MODEL = "dap-auto"

MAX_OBJECTIVE_CHARS = 7900
MAX_PRIOR_MESSAGE_CHARS = 1500
MAX_PRIOR_MESSAGES = 4


router = APIRouter(
    prefix="/openai/v1",
    tags=["DAP OpenAI Compatibility"],
)


class OpenAIMessage(BaseModel):
    model_config = {
        "extra": "allow",
    }

    role: str
    content: Any = None


class OpenAIChatCompletionRequest(BaseModel):
    model_config = {
        "extra": "allow",
    }

    model: str = DAP_AUTO_MODEL

    messages: list[OpenAIMessage] = Field(
        min_length=1,
    )

    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
    )

    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=8192,
    )

    max_completion_tokens: int | None = Field(
        default=None,
        ge=1,
        le=8192,
    )

    stream: bool = False


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if not isinstance(value, list):
        return ""

    parts: list[str] = []

    for item in value:
        if isinstance(item, str):
            text = item.strip()

            if text:
                parts.append(text)

            continue

        if not isinstance(item, dict):
            continue

        if item.get("type") not in {
            None,
            "text",
            "input_text",
        }:
            continue

        text_value = item.get("text")

        if isinstance(text_value, str):
            text = text_value.strip()

            if text:
                parts.append(text)

    return "\n".join(parts).strip()


def _build_objective(
    messages: list[OpenAIMessage],
) -> str:
    conversation: list[
        tuple[str, str]
    ] = []

    for message in messages:
        role = message.role.strip().lower()

        # DAP owns system instructions. LibreChat is only
        # a presentation client, so client system prompts
        # are deliberately not promoted to DAP authority.
        if role not in {
            "user",
            "assistant",
        }:
            continue

        text = _content_text(
            message.content
        )

        if text:
            conversation.append(
                (
                    role,
                    text,
                )
            )

    latest_user_index: int | None = None

    for index in range(
        len(conversation) - 1,
        -1,
        -1,
    ):
        if conversation[index][0] == "user":
            latest_user_index = index
            break

    if latest_user_index is None:
        raise ValueError(
            "A non-empty user message is required"
        )

    latest = conversation[
        latest_user_index
    ][1]

    prior = conversation[
        max(
            0,
            latest_user_index
            - MAX_PRIOR_MESSAGES,
        ):
        latest_user_index
    ]

    sections: list[str] = []

    if prior:
        context_lines = [
            "Recent conversation context:",
        ]

        for role, text in prior:
            label = (
                "User"
                if role == "user"
                else "Assistant"
            )

            compact = text[
                :MAX_PRIOR_MESSAGE_CHARS
            ]

            context_lines.append(
                f"{label}: {compact}"
            )

        sections.append(
            "\n".join(context_lines)
        )

    sections.extend(
        [
            "Current user request:",
            latest,
        ]
    )

    objective = "\n\n".join(
        sections
    ).strip()

    if len(objective) > MAX_OBJECTIVE_CHARS:
        keep = MAX_OBJECTIVE_CHARS - (
            len(latest) + 40
        )

        if keep > 0 and prior:
            objective = "\n\n".join(
                [
                    (
                        "Recent conversation context:\n"
                        + objective[:keep]
                    ),
                    "Current user request:",
                    latest,
                ]
            )

        objective = objective[
            -MAX_OBJECTIVE_CHARS:
        ]

    return objective


def _requested_token_budget(
    request: OpenAIChatCompletionRequest,
) -> int:
    requested = (
        request.max_completion_tokens
        or request.max_tokens
        or 700
    )

    return max(
        1,
        min(
            int(requested),
            8192,
        ),
    )


def _openai_usage(
    response: Any,
) -> dict[str, int]:
    usage = response.usage

    return {
        "prompt_tokens": (
            usage.prompt_tokens or 0
        ),
        "completion_tokens": (
            usage.completion_tokens or 0
        ),
        "total_tokens": (
            usage.total_tokens or 0
        ),
    }


async def _stream_completion_events(
    *,
    completion_id: str,
    created: int,
    content: str,
):
    common = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": DAP_AUTO_MODEL,
    }

    role_chunk = {
        **common,
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                },
                "finish_reason": None,
            }
        ],
    }

    content_chunk = {
        **common,
        "choices": [
            {
                "index": 0,
                "delta": {
                    "content": content,
                },
                "finish_reason": None,
            }
        ],
    }

    finish_chunk = {
        **common,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }

    for chunk in (
        role_chunk,
        content_chunk,
        finish_chunk,
    ):
        yield (
            "data: "
            + json.dumps(
                chunk,
                ensure_ascii=False,
            )
            + "\n\n"
        )

    yield "data: [DONE]\n\n"


@router.get("/models")
async def openai_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": DAP_AUTO_MODEL,
                "object": "model",
                "created": 0,
                "owned_by": (
                    "dipen-ai-platform"
                ),
            }
        ],
    }


@router.post(
    "/chat/completions",
    response_model=None,
)
async def openai_chat_completions(
    request: OpenAIChatCompletionRequest,
) -> Any:
    if request.model != DAP_AUTO_MODEL:
        print(
            "DAP_FACADE_REJECT|unsupported_model|"
            f"model={request.model!r}",
            flush=True,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported DAP facade model: "
                f"{request.model}. "
                f"Use {DAP_AUTO_MODEL}."
            ),
        )

    try:
        objective = _build_objective(
            request.messages
        )
    except ValueError as exc:
        print(
            "DAP_FACADE_REJECT|objective_error|"
            f"error={str(exc)!r}|"
            f"roles={[message.role for message in request.messages]!r}",
            flush=True,
        )
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    dap_request = AgentRunRequest(
        mode="smart",
        objective=objective,
        provider="ollama",
        temperature=(
            request.temperature
            if request.temperature
            is not None
            else 0.2
        ),
        max_tokens=(
            _requested_token_budget(
                request
            )
        ),
    )

    response = await agent_service.run(
        dap_request
    )

    if response.status != "completed":
        raise HTTPException(
            status_code=502,
            detail=(
                response.answer
                or "DAP agent execution failed"
            ),
        )

    created = int(
        time.time()
    )

    completion_id = (
        "chatcmpl-dap-"
        + uuid.uuid4().hex
    )

    if request.stream:
        return StreamingResponse(
            _stream_completion_events(
                completion_id=completion_id,
                created=created,
                content=response.answer,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": DAP_AUTO_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        response.answer
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": _openai_usage(
            response
        ),
    }
