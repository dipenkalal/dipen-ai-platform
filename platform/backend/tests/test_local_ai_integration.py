from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import gateway.routes as gateway_routes
from gateway.local_ai import LocalAIAdapter
from gateway.schemas import (
    LocalAIChatRequest,
    LocalAIChatResponse,
)


def _request() -> LocalAIChatRequest:
    return LocalAIChatRequest(
        messages=[
            {
                "role": "user",
                "content": "hello",
            }
        ]
    )


def _headers(
    *,
    model: str = "granite-devops",
    route: str = "general-devops",
    safety: str = "advisory-only",
    mutation: str = "none",
) -> dict[str, str]:
    return {
        "X-Local-AI-Model": model,
        "X-Local-AI-Route": route,
        "X-Local-AI-Safety": safety,
        "X-Local-AI-Mutation": mutation,
    }


def _body(
    content: str = "hello from local ai",
) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }


def test_request_forbids_client_model_override() -> None:
    with pytest.raises(
        ValidationError
    ):
        LocalAIChatRequest.model_validate(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "hello",
                    }
                ],
                "model": "qwen-coder",
            }
        )


@pytest.mark.asyncio
async def test_adapter_forces_auto_and_nonstreaming() -> None:
    seen: dict[str, object] = {}

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(
            request.content.decode(
                "utf-8"
            )
        )

        return httpx.Response(
            200,
            json=_body(),
            headers=_headers(),
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    result = await adapter.chat(
        _request()
    )

    payload = seen["payload"]

    assert (
        seen["url"]
        == (
            "http://127.0.0.1:11500/"
            "v1/chat/completions"
        )
    )

    assert isinstance(
        payload,
        dict,
    )

    assert payload["model"] == "auto"
    assert payload["stream"] is False

    assert (
        payload["messages"][0]["role"]
        == "user"
    )

    assert (
        payload["messages"][0]["content"]
        == "hello"
    )

    assert result.content == "hello from local ai"
    assert result.model == "granite-devops"
    assert result.route == "general-devops"
    assert result.safety == "advisory-only"
    assert result.mutation == "none"
    assert result.requires_human_approval is False


@pytest.mark.asyncio
async def test_human_approval_metadata_maps_true() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=_body(
                "proposed command"
            ),
            headers=_headers(
                model="qwen-coder",
                route="coding-intent",
                safety="human-approval-required",
                mutation="proposed-only",
            ),
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    result = await adapter.chat(
        _request()
    )

    assert result.model == "qwen-coder"
    assert result.route == "coding-intent"

    assert (
        result.safety
        == "human-approval-required"
    )

    assert (
        result.mutation
        == "proposed-only"
    )

    assert (
        result.requires_human_approval
        is True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_header",
    [
        "X-Local-AI-Model",
        "X-Local-AI-Route",
        "X-Local-AI-Safety",
        "X-Local-AI-Mutation",
    ],
)
async def test_missing_required_header_fails_closed(
    missing_header: str,
) -> None:
    headers = _headers()
    headers.pop(
        missing_header
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=_body(),
            headers=headers,
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await adapter.chat(
            _request()
        )

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_invalid_json_fails_closed() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
            headers=_headers(),
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await adapter.chat(
            _request()
        )

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_invalid_openai_shape_fails_closed() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [],
            },
            headers=_headers(),
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await adapter.chat(
            _request()
        )

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_timeout_maps_to_504() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "timed out",
            request=request,
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await adapter.chat(
            _request()
        )

    assert exc.value.status_code == 504


@pytest.mark.asyncio
async def test_unreachable_maps_to_502() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "unreachable",
            request=request,
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await adapter.chat(
            _request()
        )

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_non_2xx_maps_to_502() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "bad request",
            },
            headers=_headers(),
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await adapter.chat(
            _request()
        )

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_invalid_safety_pair_fails_closed() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=_body(),
            headers=_headers(
                safety="advisory-only",
                mutation="proposed-only",
            ),
        )

    adapter = LocalAIAdapter(
        transport=httpx.MockTransport(
            handler
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await adapter.chat(
            _request()
        )

    assert exc.value.status_code == 502


def test_gateway_exposes_local_ai_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAdapter:
        async def chat(
            self,
            request: LocalAIChatRequest,
        ) -> LocalAIChatResponse:
            return LocalAIChatResponse(
                content="offline",
                model="granite-devops",
                route="general-devops",
                safety="advisory-only",
                mutation="none",
                requires_human_approval=False,
            )

    monkeypatch.setattr(
        gateway_routes,
        "local_ai_adapter",
        FakeAdapter(),
    )

    app = FastAPI()
    app.include_router(
        gateway_routes.router
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/local-ai/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ]
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "content": "offline",
        "model": "granite-devops",
        "route": "general-devops",
        "safety": "advisory-only",
        "mutation": "none",
        "requires_human_approval": False,
    }
