from fastapi import FastAPI
from fastapi.testclient import TestClient

from history import chat_routes
from history.chat_repository import (
    ChatHistoryRepository,
)
from history.chat_service import (
    ChatHistoryService,
)
from history.database import HistoryDatabase


def make_client(
    tmp_path,
    monkeypatch,
) -> TestClient:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    repository = ChatHistoryRepository(
        database
    )

    service = ChatHistoryService(
        repository
    )

    monkeypatch.setattr(
        chat_routes,
        "chat_history_service",
        service,
    )

    app = FastAPI()

    app.include_router(
        chat_routes.router
    )

    return TestClient(app)


def test_chat_api_lifecycle(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(
        tmp_path,
        monkeypatch,
    )

    created = client.post(
        "/api/v1/chat/conversations",
        json={
            "title": "System health",
            "preferred_role_id": "auto",
        },
    )

    assert created.status_code == 201

    conversation = created.json()

    conversation_id = (
        conversation["conversation_id"]
    )

    user = client.post(
        (
            "/api/v1/chat/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "role": "user",
            "content": (
                "Check the DAP system health."
            ),
        },
    )

    assert user.status_code == 201
    assert user.json()["sequence"] == 1

    assistant = client.post(
        (
            "/api/v1/chat/conversations/"
            f"{conversation_id}/messages"
        ),
        json={
            "role": "assistant",
            "content": "",
            "employee_role_id": (
                "systems-engineer"
            ),
            "employee_title": (
                "Systems Engineer"
            ),
            "department_name": (
                "Infrastructure and Operations"
            ),
            "machine_agent_id": (
                "system-agent"
            ),
            "status": "running",
        },
    )

    assert assistant.status_code == 201

    assistant_body = assistant.json()

    message_id = (
        assistant_body["message_id"]
    )

    updated_message = client.patch(
        (
            "/api/v1/chat/conversations/"
            f"{conversation_id}/messages/"
            f"{message_id}"
        ),
        json={
            "content": (
                "DAP system health is good."
            ),
            "model": "qwen3:1.7b",
            "routing_confidence": 0.99,
            "status": "completed",
        },
    )

    assert (
        updated_message.status_code
        == 200
    )

    assert (
        updated_message.json()["status"]
        == "completed"
    )

    detail = client.get(

            "/api/v1/chat/conversations/"
            f"{conversation_id}"

    )

    assert detail.status_code == 200

    assert (
        len(
            detail.json()["messages"]
        )
        == 2
    )

    listing = client.get(
        "/api/v1/chat/conversations"
    )

    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    renamed = client.patch(
        (
            "/api/v1/chat/conversations/"
            f"{conversation_id}"
        ),
        json={
            "title": (
                "DAP system health"
            ),
        },
    )

    assert renamed.status_code == 200

    assert (
        renamed.json()["title"]
        == "DAP system health"
    )

    deleted = client.delete(

            "/api/v1/chat/conversations/"
            f"{conversation_id}"

    )

    assert deleted.status_code == 200
    assert deleted.json()["deleted"]

    missing = client.get(

            "/api/v1/chat/conversations/"
            f"{conversation_id}"

    )

    assert missing.status_code == 404


def test_missing_chat_records_return_404(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(
        tmp_path,
        monkeypatch,
    )

    missing_conversation = client.get(

            "/api/v1/chat/conversations/"
            "missing"

    )

    assert (
        missing_conversation.status_code
        == 404
    )

    missing_message = client.patch(
        (
            "/api/v1/chat/conversations/"
            "missing/messages/missing"
        ),
        json={
            "content": "Nope",
        },
    )

    assert (
        missing_message.status_code
        == 404
    )
