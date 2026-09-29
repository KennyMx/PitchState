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


def test_upload_ownership_cancellation_and_quota(tmp_path, monkeypatch):
    from server.pitchstate import api

    monkeypatch.setattr(api, "JOBS", tmp_path)
    monkeypatch.setattr(api, "jobs", {})
    submitted = []
    monkeypatch.setattr(api.executor, "submit", lambda *args: submitted.append(args))
    monkeypatch.setenv("PITCHSTATE_DAILY_JOB_LIMIT", "1")
    owner, stranger = TestClient(app), TestClient(app)
    owner.get("/api/health")
    stranger.get("/api/health")
    identity = "a" * 32
    response = owner.post(
        "/api/jobs",
        data={"request_id": identity, "use_jev": "false"},
        files={"video": ("play.webm", b"test fixture", "video/webm")},
    )
    assert response.status_code == 202
    assert len(submitted) == 1
    assert "owner" not in response.json()
    for suffix in ("", "/analysis", "/video"):
        assert stranger.get(f"/api/jobs/{identity}{suffix}").status_code == 404
    assert stranger.delete(f"/api/jobs/{identity}").status_code == 404
    assert owner.get(f"/api/jobs/{identity}/analysis").status_code == 409
    assert owner.delete(f"/api/jobs/{identity}").status_code == 200
    assert api.jobs[identity]["cancel"].is_set()
    assert owner.get(f"/api/jobs/{identity}").json()["status"] == "cancelled"
    assert owner.post("/api/jobs", files={"video": ("play.mp4", b"x")}).status_code == 429
