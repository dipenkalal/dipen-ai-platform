import history.service as service
import pytest
from fastapi import HTTPException


def test_save_forwards_to_repository(monkeypatch):
    request = object()
    response = object()
    expected = object()

    captured = {}

    def fake_save(*, request, response, error):
        captured["request"] = request
        captured["response"] = response
        captured["error"] = error
        return expected

    monkeypatch.setattr(
        service.agent_run_repository,
        "save",
        fake_save,
    )

    result = service.agent_run_history_service.save(
        request,
        response,
        error="boom",
    )

    assert result is expected
    assert captured == {
        "request": request,
        "response": response,
        "error": "boom",
    }


def test_get_returns_record(monkeypatch):
    record = object()

    monkeypatch.setattr(
        service.agent_run_repository,
        "get",
        lambda run_id: record,
    )

    assert service.agent_run_history_service.get("abc") is record


def test_get_raises_404(monkeypatch):
    monkeypatch.setattr(
        service.agent_run_repository,
        "get",
        lambda run_id: None,
    )

    with pytest.raises(HTTPException) as exc:
        service.agent_run_history_service.get("missing")

    assert exc.value.status_code == 404
    assert "missing" in exc.value.detail


def test_list_returns_response(monkeypatch):
    runs = [
        {
            "run_id": "run-1",
            "agent_id": "agent",
            "objective": "Summarise the system status",
            "model": "qwen",
            "provider": "ollama",
            "status": "completed",
            "answer_preview": "Everything is healthy.",
            "error": None,
            "step_count": 2,
            "source_count": 1,
            "total_tokens": 120,
            "latency_ms": 45.5,
            "started_at": "2026-07-28T10:00:00Z",
            "completed_at": "2026-07-28T10:00:05Z",
            "created_at": "2026-07-28T10:00:00Z",
        },
        {
            "run_id": "run-2",
            "agent_id": "agent",
            "objective": "Check the failed workflow",
            "model": "llama",
            "provider": "ollama",
            "status": "failed",
            "answer_preview": "",
            "error": "Workflow failed",
            "step_count": 1,
            "source_count": 0,
            "total_tokens": None,
            "latency_ms": 12.0,
            "started_at": "2026-07-28T11:00:00Z",
            "completed_at": "2026-07-28T11:00:01Z",
            "created_at": "2026-07-28T11:00:00Z",
        },
    ]

    captured = {}

    def fake_list(
        *,
        limit,
        offset,
        agent_id,
        status,
        model,
        search,
    ):
        captured.update(
            {
                "limit": limit,
                "offset": offset,
                "agent_id": agent_id,
                "status": status,
                "model": model,
                "search": search,
            }
        )
        return runs, 27

    monkeypatch.setattr(
        service.agent_run_repository,
        "list",
        fake_list,
    )

    response = service.agent_run_history_service.list(
        limit=10,
        offset=5,
        agent_id="agent",
        status="success",
        model="qwen",
        search="hello",
    )

    assert len(response.runs) == 2
    assert response.runs[0].run_id == "run-1"
    assert response.runs[1].run_id == "run-2"
    assert response.total == 27
    assert response.limit == 10
    assert response.offset == 5
    assert response.runs[0].status == "completed"
    assert response.runs[1].status == "failed"

    assert captured == {
        "limit": 10,
        "offset": 5,
        "agent_id": "agent",
        "status": "success",
        "model": "qwen",
        "search": "hello",
    }


def test_delete_success(monkeypatch):
    monkeypatch.setattr(
        service.agent_run_repository,
        "delete",
        lambda run_id: True,
    )

    response = service.agent_run_history_service.delete("run123")

    assert response.deleted is True
    assert response.run_id == "run123"


def test_delete_missing(monkeypatch):
    monkeypatch.setattr(
        service.agent_run_repository,
        "delete",
        lambda run_id: False,
    )

    with pytest.raises(HTTPException) as exc:
        service.agent_run_history_service.delete("missing")

    assert exc.value.status_code == 404
    assert "missing" in exc.value.detail


def test_clear_returns_deleted_count(monkeypatch):
    monkeypatch.setattr(
        service.agent_run_repository,
        "clear",
        lambda: 42,
    )

    response = service.agent_run_history_service.clear()

    assert response.deleted_count == 42
