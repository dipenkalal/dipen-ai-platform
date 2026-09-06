from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from gateway.schemas import (
    LocalAIChatRequest,
    LocalAIChatResponse,
)


LOCAL_AI_CHAT_URL = (
    "http://127.0.0.1:11500/"
    "v1/chat/completions"
)

LOCAL_AI_TIMEOUT_SECONDS = 120.0

_REQUIRED_HEADERS = (
    "X-Local-AI-Model",
    "X-Local-AI-Route",
    "X-Local-AI-Safety",
    "X-Local-AI-Mutation",
)


class LocalAIAdapter:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport

    async def chat(
        self,
        request: LocalAIChatRequest,
    ) -> LocalAIChatResponse:
        payload = {
            "model": "auto",
            "stream": False,
            "messages": [
                message.model_dump(
                    exclude_none=True,
                )
                for message in request.messages
            ],
        }

        try:
            async with httpx.AsyncClient(
                timeout=LOCAL_AI_TIMEOUT_SECONDS,
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    LOCAL_AI_CHAT_URL,
                    json=payload,
                )

        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="Local AI request timed out",
            ) from exc

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail="Local AI is unavailable",
            ) from exc

        if not (
            200
            <= response.status_code
            < 300
        ):
            raise HTTPException(
                status_code=502,
                detail="Local AI upstream request failed",
            )

        metadata = self._required_metadata(
            response
        )

        body = self._json_body(
            response
        )

        content = self._content(
            body
        )

        safety = metadata[
            "X-Local-AI-Safety"
        ]

        mutation = metadata[
            "X-Local-AI-Mutation"
        ]

        self._validate_safety_pair(
            safety=safety,
            mutation=mutation,
        )

        return LocalAIChatResponse(
            content=content,
            model=metadata[
                "X-Local-AI-Model"
            ],
            route=metadata[
                "X-Local-AI-Route"
            ],
            safety=safety,
            mutation=mutation,
            requires_human_approval=(
                safety
                == "human-approval-required"
            ),
        )

    @staticmethod
    def _required_metadata(
        response: httpx.Response,
    ) -> dict[str, str]:
        metadata: dict[str, str] = {}

        for name in _REQUIRED_HEADERS:
            value = response.headers.get(
                name
            )

            if (
                value is None
                or not value.strip()
            ):
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Local AI response is missing "
                        "required safety metadata"
                    ),
                )

            metadata[name] = value.strip()

        return metadata

    @staticmethod
    def _json_body(
        response: httpx.Response,
    ) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Local AI returned invalid JSON"
                ),
            ) from exc

        if not isinstance(
            body,
            dict,
        ):
            raise HTTPException(
                status_code=502,
                detail=(
                    "Local AI returned an invalid "
                    "response shape"
                ),
            )

        return body

    @staticmethod
    def _content(
        body: dict[str, Any],
    ) -> str:
        try:
            choices = body["choices"]

            if not (
                isinstance(choices, list)
                and choices
            ):
                raise TypeError

            choice = choices[0]

            if not isinstance(
                choice,
                dict,
            ):
                raise TypeError

            message = choice["message"]

            if not isinstance(
                message,
                dict,
            ):
                raise TypeError

            content = message["content"]

            if not isinstance(
                content,
                str,
            ):
                raise TypeError

            return content

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Local AI returned an invalid "
                    "OpenAI response shape"
                ),
            ) from exc

    @staticmethod
    def _validate_safety_pair(
        *,
        safety: str,
        mutation: str,
    ) -> None:
        valid_pairs = {
            (
                "advisory-only",
                "none",
            ),
            (
                "human-approval-required",
                "proposed-only",
            ),
        }

        if (
            safety,
            mutation,
        ) not in valid_pairs:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Local AI returned invalid "
                    "safety metadata"
                ),
            )


local_ai_adapter = LocalAIAdapter()
