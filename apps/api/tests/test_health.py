"""Health endpoint tests."""

from fastapi.testclient import TestClient


def test_health_reports_ok(client: TestClient):
    """The basic health probe answers without touching the database."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_probe_reports_alive(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_probe_reports_database_reachable(client: TestClient):
    """Readiness must actually exercise the database connection."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_root_describes_the_service(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "EPIRO API"
