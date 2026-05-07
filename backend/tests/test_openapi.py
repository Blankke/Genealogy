from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_contains_core_routes() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/auth/register" in paths
    assert "/admin/dashboard" in paths
    assert "/genealogies" in paths
    assert "/genealogies/{genealogy_id}/members" in paths
    assert "/members/{member_id}/ancestors" in paths
    assert "/genealogies/{genealogy_id}/relationship-path" in paths
