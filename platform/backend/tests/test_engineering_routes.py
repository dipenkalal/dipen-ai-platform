from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from engineering import routes
from engineering.engineering_workspace import EngineeringWorkspaceService


def engineering_task(task_id: str) -> TaskLedgerRecord:
    now = datetime.now(timezone.utc)
    return TaskLedgerRecord(
        task_id=task_id,
        task_type="agent",
        objective="Inspect a bounded Engineering Agent task.",
        status="assigned",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id="delegation-route-test",
        parent_task_id="parent-route-test",
        created_at=now,
        updated_at=now,
    )


def client(tmp_path: Path) -> TestClient:
    truth = AgentTruthRepository(tmp_path / "agent-truth.db")
    truth.upsert_task(engineering_task("engineering-route-test"))
    routes.workspace_service = EngineeringWorkspaceService(truth)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_workspace_routes_expose_get_only_read_model(tmp_path: Path) -> None:
    test_client = client(tmp_path)

    response = test_client.get("/api/v1/engineering/workspace")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["execution_controls_exposed"] is False
    assert payload["summary"]["total"] == 1

    detail = test_client.get(
        "/api/v1/engineering/workspace/engineering-route-test"
    )
    assert detail.status_code == 200
    assert detail.json()["task"]["task_id"] == "engineering-route-test"

    for method in ("post", "put", "patch", "delete"):
        blocked = getattr(test_client, method)("/api/v1/engineering/workspace")
        assert blocked.status_code == 405


def test_workspace_detail_returns_404_for_unknown_task(tmp_path: Path) -> None:
    test_client = client(tmp_path)

    response = test_client.get("/api/v1/engineering/workspace/missing")

    assert response.status_code == 404
