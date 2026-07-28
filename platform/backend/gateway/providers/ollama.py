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

        self.thinking_enabled = self._read_boolean_env(
            "OLLAMA_THINKING_ENABLED",
            default=False,
        )

        self.timeout = httpx.Timeout(
            connect=10.0,
            read=600.0,
            write=30.0,
            pool=10.0,
        )

    @staticmethod
    def _read_boolean_env(
        name: str,
        default: bool,
    ) -> bool:
        raw_value = os.getenv(name)

        if raw_value is None:
            return default

        return raw_value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return value.strip()

    @staticmethod
    def _calculate_total_tokens(
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> int | None:
        if prompt_tokens is None or completion_tokens is None:
            return None

        return prompt_tokens + completion_tokens

    @staticmethod
    def _empty_response_error(
        *,
        model: str,
        done_reason: str | None,
        has_thinking: bool,
    ) -> RuntimeError:
        if done_reason == "length" and has_thinking:
            return RuntimeError(
                f"Model '{model}' exhausted its token budget "
                "during reasoning before producing a final answer. "
                "Thinking is disabled by default in DAP. If it was "
                "explicitly enabled, increase max_tokens or disable "
                "OLLAMA_THINKING_ENABLED."
            )

        if done_reason == "length":
            return RuntimeError(
                f"Model '{model}' reached its token limit before "
                "producing a final answer. Increase max_tokens and "
                "try again."
            )

        if has_thinking:
            return RuntimeError(
                f"Model '{model}' returned reasoning output but no "
                "final answer."
            )

        return RuntimeError(f"Model '{model}' returned an empty response.")

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
        async with httpx.AsyncClient(
            timeout=self.timeout,
        ) as client:
            response = await client.get(
                f"{self.base_url}/api/tags",
            )
            response.raise_for_status()

        payload: dict[str, Any] = response.json()
        models: list[ModelInfo] = []

        for model in payload.get("models", []):
            if not isinstance(model, dict):
                continue

            model_id = str(model.get("name", "unknown"))

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
            "messages": [message.model_dump() for message in request.messages],
            "stream": stream,
            "think": self.thinking_enabled,
            "options": options,
        }

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        model = request.model or self.default_model
        payload = self._create_payload(
            request,
            stream=False,
        )

        started = time.perf_counter()

        async with httpx.AsyncClient(
            timeout=self.timeout,
        ) as client:
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

        raw_message = result.get("message")
        message = raw_message if isinstance(raw_message, dict) else {}

        content = self._clean_text(message.get("content"))
        thinking = self._clean_text(message.get("thinking"))

        done_reason_value = result.get("done_reason")
        done_reason = (
            str(done_reason_value) if done_reason_value is not None else None
        )

        if not content:
            raise self._empty_response_error(
                model=str(result.get("model", model)),
                done_reason=done_reason,
                has_thinking=bool(thinking),
            )

        prompt_tokens = result.get("prompt_eval_count")
        completion_tokens = result.get("eval_count")

        total_tokens = self._calculate_total_tokens(
            prompt_tokens,
            completion_tokens,
        )

        return ChatResponse(
            provider=self.name,
            model=str(result.get("model", model)),
            message=ChatMessage(
                role="assistant",
                content=content,
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
        payload = self._create_payload(
            request,
            stream=True,
        )

        started = time.perf_counter()
        content_received = False
        thinking_received = False

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

                        raw_message = chunk.get("message")
                        message = (
                            raw_message
                            if isinstance(
                                raw_message,
                                dict,
                            )
                            else {}
                        )

                        content = message.get("content")
                        thinking = message.get("thinking")

                        if isinstance(thinking, str) and thinking:
                            thinking_received = True

                        if isinstance(content, str) and content:
                            content_received = True

                            content_event = {
                                "type": "content",
                                "content": content,
                            }

                            yield (json.dumps(content_event) + "\n")

                        if chunk.get("done") is not True:
                            continue

                        prompt_tokens = chunk.get("prompt_eval_count")
                        completion_tokens = chunk.get("eval_count")

                        total_tokens = self._calculate_total_tokens(
                            prompt_tokens,
                            completion_tokens,
                        )

                        latency_ms = round(
                            (time.perf_counter() - started) * 1000,
                            2,
                        )

                        done_reason_value = chunk.get("done_reason")
                        done_reason = (
                            str(done_reason_value)
                            if done_reason_value is not None
                            else None
                        )

                        if not content_received:
                            error = self._empty_response_error(
                                model=str(
                                    chunk.get(
                                        "model",
                                        model,
                                    )
                                ),
                                done_reason=done_reason,
                                has_thinking=(thinking_received),
                            )

                            error_event = {
                                "type": "error",
                                "error": str(error),
                            }

                            yield (json.dumps(error_event) + "\n")
                            return

                        final_event = {
                            "type": "done",
                            "provider": self.name,
                            "model": str(
                                chunk.get(
                                    "model",
                                    model,
                                )
                            ),
                            "done_reason": done_reason,
                            "usage": {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                                "latency_ms": latency_ms,
                            },
                        }

                        yield (json.dumps(final_event) + "\n")
                        return

        except httpx.HTTPStatusError as exc:
            response_body = ""

            try:
                response_body = exc.response.text.strip()
            except Exception:
                response_body = ""

            error_message = (
                "Ollama returned HTTP " f"{exc.response.status_code}"
            )

            if response_body:
                error_message += f": {response_body[:500]}"

            error_event = {
                "type": "error",
                "error": error_message,
            }

            yield json.dumps(error_event) + "\n"

        except httpx.HTTPError as exc:
            error_event = {
                "type": "error",
                "error": ("Ollama connection failed: " f"{exc}"),
            }

            yield json.dumps(error_event) + "\n"

        except Exception as exc:
            error_event = {
                "type": "error",
                "error": ("Ollama generation failed: " f"{exc}"),
            }

            yield json.dumps(error_event) + "\n"


ollama_provider = OllamaProvider()
