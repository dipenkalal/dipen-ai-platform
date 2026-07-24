import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from gateway.providers.base import AIProvider
from gateway.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ModelInfo,
    UsageMetrics,
)


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ).rstrip("/")

        self.default_model = os.getenv(
            "OLLAMA_DEFAULT_MODEL",
            "qwen3:1.7b",
        )

        self.timeout = httpx.Timeout(
            connect=10.0,
            read=600.0,
            write=30.0,
            pool=10.0,
        )

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                )
                return response.is_success
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/tags",
            )
            response.raise_for_status()

        payload: dict[str, Any] = response.json()
        models: list[ModelInfo] = []

        for model in payload.get("models", []):
            model_id = model.get("name", "unknown")

            models.append(
                ModelInfo(
                    provider=self.name,
                    id=model_id,
                    name=model_id,
                    local=True,
                    available=True,
                    size_bytes=model.get("size"),
                )
            )

        return models

    def _create_payload(
        self,
        request: ChatRequest,
        stream: bool,
    ) -> dict[str, Any]:
        model = request.model or self.default_model

        options: dict[str, Any] = {
            "temperature": request.temperature,
        }

        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        return {
            "model": model,
            "messages": [
                message.model_dump()
                for message in request.messages
            ],
            "stream": stream,
            "options": options,
        }

    async def chat(self, request: ChatRequest) -> ChatResponse:
        model = request.model or self.default_model
        payload = self._create_payload(request, stream=False)

        started = time.perf_counter()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()

        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        result: dict[str, Any] = response.json()
        message = result.get("message", {})

        prompt_tokens = result.get("prompt_eval_count")
        completion_tokens = result.get("eval_count")

        total_tokens = None

        if (
            prompt_tokens is not None
            and completion_tokens is not None
        ):
            total_tokens = prompt_tokens + completion_tokens

        return ChatResponse(
            provider=self.name,
            model=result.get("model", model),
            message=ChatMessage(
                role="assistant",
                content=message.get("content", ""),
            ),
            usage=UsageMetrics(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            ),
        )

    async def stream_chat(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        model = request.model or self.default_model
        payload = self._create_payload(request, stream=True)
        started = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        try:
                            chunk: dict[str, Any] = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        message = chunk.get("message", {})
                        content = message.get("content", "")

                        if content:
                            event = {
                                "type": "content",
                                "content": content,
                            }

                            yield json.dumps(event) + "\n"

                        if chunk.get("done") is True:
                            prompt_tokens = chunk.get(
                                "prompt_eval_count"
                            )
                            completion_tokens = chunk.get(
                                "eval_count"
                            )

                            total_tokens = None

                            if (
                                prompt_tokens is not None
                                and completion_tokens is not None
                            ):
                                total_tokens = (
                                    prompt_tokens
                                    + completion_tokens
                                )

                            latency_ms = round(
                                (
                                    time.perf_counter()
                                    - started
                                )
                                * 1000,
                                2,
                            )

                            final_event = {
                                "type": "done",
                                "provider": self.name,
                                "model": chunk.get(
                                    "model",
                                    model,
                                ),
                                "usage": {
                                    "prompt_tokens": prompt_tokens,
                                    "completion_tokens":
                                        completion_tokens,
                                    "total_tokens": total_tokens,
                                    "latency_ms": latency_ms,
                                },
                            }

                            yield json.dumps(final_event) + "\n"

        except httpx.HTTPStatusError as exc:
            error_event = {
                "type": "error",
                "error": (
                    "Ollama returned HTTP "
                    f"{exc.response.status_code}"
                ),
            }

            yield json.dumps(error_event) + "\n"

        except httpx.HTTPError as exc:
            error_event = {
                "type": "error",
                "error": f"Ollama connection failed: {exc}",
            }

            yield json.dumps(error_event) + "\n"
