from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.truth_repository import AgentTruthRepository
from engineering import routes
from engineering.engineering_audit_repository import EngineeringAuditRepository
from engineering.engineering_owner_review_repository import EngineeringOwnerReviewRepository
from engineering.engineering_workspace import EngineeringWorkspaceService
from tests.test_engineering_owner_review import engineering_task, successful_evidence


def client(tmp_path: Path) -> tuple[TestClient, AgentTruthRepository]:
    truth = AgentTruthRepository(tmp_path / "agent-truth.db")
    task = engineering_task()
    truth.upsert_task(task)
    audit = EngineeringAuditRepository(truth)
    audit.persist(successful_evidence())
    review = EngineeringOwnerReviewRepository(truth, audit)

    routes.agent_truth_repository = truth
    routes.workspace_service = EngineeringWorkspaceService(truth)
    routes.audit_repository = audit
    routes.owner_review_repository = review

    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app), truth


def test_review_routes_record_owner_decision_without_execution(tmp_path: Path) -> None:
    test_client, truth = client(tmp_path)
    task_before = truth.get_task("phase11i-task")

    listing = test_client.get("/api/v1/engineering/reviews")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["review_count"] == 1
    assert payload["pending_count"] == 1
    assert payload["merge_controls_exposed"] is False
    assert payload["deployment_controls_exposed"] is False
    assert payload["guardian_controls_exposed"] is False

    evidence_id = payload["reviews"][0]["package"]["evidence_id"]
    decision = test_client.post(
        f"/api/v1/engineering/reviews/{evidence_id}/decision",
        json={
            "decision": "approve",
            "reason": "Owner reviewed the bounded evidence package.",
        },
    )
    assert decision.status_code == 200
    decided = decision.json()["decision"]
    assert decided["decision"] == "approve"
    assert decided["owner_merge_action_still_required"] is True
    assert decided["git_write_performed"] is False
    assert decided["pull_request_merged"] is False
    assert decided["main_merge_performed"] is False
    assert decided["deployment_performed"] is False
    assert decided["guardian_contacted"] is False
    assert decided["task_ledger_mutated"] is False

    after = test_client.get(f"/api/v1/engineering/reviews/{evidence_id}")
    assert after.status_code == 200
    assert after.json()["decision"]["decision"] == "approve"
    assert truth.get_task("phase11i-task") == task_before


def test_conflicting_review_decision_returns_409(tmp_path: Path) -> None:
    test_client, _truth = client(tmp_path)
    evidence_id = test_client.get("/api/v1/engineering/reviews").json()["reviews"][0][
        "package"
    ]["evidence_id"]
    approved = test_client.post(
        f"/api/v1/engineering/reviews/{evidence_id}/decision",
        json={"decision": "approve", "reason": "Accepted."},
    )
    assert approved.status_code == 200

    rejected = test_client.post(
        f"/api/v1/engineering/reviews/{evidence_id}/decision",
        json={"decision": "reject", "reason": "Changed decision."},
    )
    assert rejected.status_code == 409


def test_reject_route_requires_reason(tmp_path: Path) -> None:
    test_client, _truth = client(tmp_path)
    evidence_id = test_client.get("/api/v1/engineering/reviews").json()["reviews"][0][
        "package"
    ]["evidence_id"]

    response = test_client.post(
        f"/api/v1/engineering/reviews/{evidence_id}/decision",
        json={"decision": "reject", "reason": ""},
    )

    assert response.status_code == 422
