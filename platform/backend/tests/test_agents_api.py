from app import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "online"
    assert "version" in body
    assert "name" in body


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"
    assert "timestamp" in body
    assert "version" in body


def test_list_agents():
    response = client.get("/api/v1/agents")

    assert response.status_code == 200

    body = response.json()

    assert "agents" in body
    assert isinstance(body["agents"], list)
    assert len(body["agents"]) > 0


def test_list_tools():
    response = client.get("/api/v1/tools")

    assert response.status_code == 200

    body = response.json()

    assert "tools" in body
    assert isinstance(body["tools"], list)
