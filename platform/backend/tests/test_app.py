from unittest.mock import patch

import pytest
from app import (
    APP_VERSION,
    app,
    resolve_collector_result,
)
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.asyncio
async def test_resolve_collector_result_awaitable():
    async def async_value():
        return {"status": "ok"}

    result = await resolve_collector_result(async_value())

    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_resolve_collector_result_sync_value():
    value = {"status": "ok"}

    result = await resolve_collector_result(value)

    assert result is value


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Dipen AI Platform API",
        "version": APP_VERSION,
        "status": "online",
    }


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"
    assert body["version"] == APP_VERSION
    assert "timestamp" in body


def test_status_endpoint_with_sync_collectors():
    system_result = {
        "cpu": {"usage_percent": 25.0},
    }
    ollama_result = {
        "status": "online",
    }

    with (
        patch(
            "app.get_system_status",
            return_value=system_result,
        ) as mocked_system,
        patch(
            "app.get_ollama_status",
            return_value=ollama_result,
        ) as mocked_ollama,
    ):
        response = client.get("/api/status")

    assert response.status_code == 200

    body = response.json()

    assert body["version"] == APP_VERSION
    assert body["system"] == system_result
    assert body["ollama"] == ollama_result
    assert "timestamp" in body

    mocked_system.assert_called_once_with()
    mocked_ollama.assert_called_once_with()


def test_status_endpoint_with_async_collectors():
    async def async_system_status():
        return {
            "cpu": {"usage_percent": 40.0},
        }

    async def async_ollama_status():
        return {
            "status": "online",
            "models": 2,
        }

    with (
        patch(
            "app.get_system_status",
            side_effect=async_system_status,
        ) as mocked_system,
        patch(
            "app.get_ollama_status",
            side_effect=async_ollama_status,
        ) as mocked_ollama,
    ):
        response = client.get("/api/status")

    assert response.status_code == 200

    body = response.json()

    assert body["system"] == {
        "cpu": {"usage_percent": 40.0},
    }
    assert body["ollama"] == {
        "status": "online",
        "models": 2,
    }

    mocked_system.assert_called_once_with()
    mocked_ollama.assert_called_once_with()
