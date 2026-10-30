import pytest
from tests.conftest import login_user, TEST_ADMIN_PASSWORD, TEST_CONTROLLER_TOKEN

def test_login_success(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@orbitron.local", "password": TEST_ADMIN_PASSWORD},
        headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "admin@orbitron.local"
    assert "csrf_token" in data
    assert data["expires_at"].endswith("Z")
    assert "orbitron_session" in client.cookies

def test_login_invalid_password(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@orbitron.local", "password": "WrongPassword!"},
        headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

def test_session_retrieval(client):
    login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    resp = client.get("/api/v1/auth/session")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "admin@orbitron.local"

def test_logout(client):
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]
    resp = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf}
    )
    assert resp.status_code == 204
    # Attempting to retrieve session after logout should fail with 401
    resp_after = client.get("/api/v1/auth/session")
    assert resp_after.status_code == 401

def test_csrf_required_for_mutations(client):
    login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    # Mutation without CSRF token
    resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": 1000000,
            "deadline_at": "2026-10-31T08:00:00Z",
            "priority": "routine",
            "allow_split": True
        },
        headers={"Origin": "http://localhost:5173", "Idempotency-Key": "test-key-no-csrf"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_INVALID"

def test_origin_validation(client):
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]
    resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": 1000000,
            "deadline_at": "2026-10-31T08:00:00Z",
            "priority": "routine",
            "allow_split": True
        },
        headers={
            "Origin": "http://evil-origin.test",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "test-key-evil-origin"
        }
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"

def test_service_bearer_auth(client):
    # Valid service bearer token
    resp = client.get("/api/v1/service/work", headers={"Authorization": f"Bearer {TEST_CONTROLLER_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["principal_id"] == "sim-controller"

    # Invalid service bearer token
    resp_bad = client.get("/api/v1/service/work", headers={"Authorization": "Bearer bad_token"})
    assert resp_bad.status_code == 401
