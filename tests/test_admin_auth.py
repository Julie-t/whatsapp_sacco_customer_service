"""Unit and integration tests for System 11 Admin Authentication & Tenant Isolation."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.admin.admin_auth_service import hash_password, verify_password, create_access_token, decode_access_token

client = TestClient(app)


def test_password_hashing_and_verification():
    raw = "SecureSaccoPassword123!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert ":" in hashed
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_token_creation_and_decoding():
    token = create_access_token(
        admin_id="admin_001",
        username="admin",
        sacco_id="demo_sacco",
        role="admin",
    )
    assert isinstance(token, str)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["admin_id"] == "admin_001"
    assert payload["username"] == "admin"
    assert payload["sacco_id"] == "demo_sacco"
    assert payload["role"] == "admin"


def test_login_success_and_me():
    # Login with seeded admin credentials
    res = client.post("/api/admin/auth/login", json={"username": "admin", "password": "SaccoAdmin2026!"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert data["sacco_id"] == "demo_sacco"

    token = data["access_token"]
    # Access protected /me endpoint
    me_res = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "admin"
    assert me_data["role"] == "admin"


def test_login_invalid_password_rejected():
    res = client.post("/api/admin/auth/login", json={"username": "admin", "password": "IncorrectPassword"})
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]


def test_unauthorized_access_blocked():
    # Access without bearer token
    res = client.get("/api/admin/analytics/overview")
    assert res.status_code == 401

    # Access with forged/invalid token
    res2 = client.get("/api/admin/analytics/overview", headers={"Authorization": "Bearer forged_invalid_token"})
    assert res2.status_code == 401
