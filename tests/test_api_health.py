from fastapi.testclient import TestClient

from presentations.http_api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
