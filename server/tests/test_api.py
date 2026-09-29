from fastapi.testclient import TestClient
from server.pitchstate.api import app


def test_origin_and_session_boundary():
    client = TestClient(app)
    assert (
        client.get("/api/health", headers={"origin": "https://untrusted.example"}).status_code
        == 403
    )
    assert client.get("/api/jobs/nonexistent").status_code == 404
    result = client.get("/api/health")
    assert result.status_code == 200
    assert "pitchstate_session" in client.cookies
    assert "api_key" not in result.text.lower()


def test_rejects_oversized_request_before_parsing_upload():
    response = TestClient(app).post("/api/jobs", headers={"content-length": str(200 * 1024 * 1024)})
    assert response.status_code == 413
