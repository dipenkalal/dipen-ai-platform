import pytest
import tools.system_tools as system_tools


@pytest.mark.asyncio
async def test_resolve_result_returns_plain_value():
    result = await system_tools.resolve_result(123)

    assert result == 123


@pytest.mark.asyncio
async def test_resolve_result_awaits_coroutine():
    async def coro():
        return "done"

    result = await system_tools.resolve_result(coro())

    assert result == "done"


@pytest.mark.asyncio
async def test_system_status_tool_success(monkeypatch):
    async def fake_system():
        return {
            "cpu": 15,
            "memory": 42,
        }

    async def fake_ollama():
        return {
            "healthy": True,
        }

    monkeypatch.setattr(
        system_tools,
        "get_system_status",
        fake_system,
    )

    monkeypatch.setattr(
        system_tools,
        "get_ollama_status",
        fake_ollama,
    )

    tool = system_tools.SystemStatusTool()

    result = await tool.execute({})

    assert result.success is True
    assert result.tool_id == "system.status"
    assert result.output["system"]["cpu"] == 15
    assert result.output["ollama"]["healthy"] is True


@pytest.mark.asyncio
async def test_system_status_tool_failure(monkeypatch):
    async def failing_system():
        raise RuntimeError("collector failed")

    monkeypatch.setattr(
        system_tools,
        "get_system_status",
        failing_system,
    )

    tool = system_tools.SystemStatusTool()

    result = await tool.execute({})

    assert result.success is False
    assert result.tool_id == "system.status"
    assert result.error == "collector failed"
