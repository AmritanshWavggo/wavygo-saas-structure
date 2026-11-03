from __future__ import annotations

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import mongodb
from app.main import app
from app.modules.auth.service import hash_password


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-must-be-at-least-32-bytes-long!")
    monkeypatch.setattr(settings, "mongodb_uri", "mongodb://mock")

    client = mongomock.MongoClient()
    db = client[settings.mongodb_database]

    from app.modules.auth import deps as auth_deps
    from app.modules.auth import router as auth_router
    from app.modules.vehicles import router as vehicles_router

    monkeypatch.setattr(mongodb, "get_database", lambda c=None: db)
    monkeypatch.setattr(mongodb, "create_mongo_client", lambda: client)
    monkeypatch.setattr(auth_deps, "get_database", lambda c=None: db)
    monkeypatch.setattr(auth_router, "get_database", lambda c=None: db)
    monkeypatch.setattr(vehicles_router, "get_database", lambda c=None: db)

    # Seed one tenant and staff + owner
    pwd = hash_password("Secret12345")
    tenant_id = db.tenants.insert_one({"name": "Test Tenant", "slug": "test-tenant"}).inserted_id
    db.users.insert_one({"tenantId": tenant_id, "email": "owner@example.com", "role": "owner", "isActive": True, "passwordHash": pwd})
    db.users.insert_one({"tenantId": tenant_id, "email": "staff@example.com", "role": "staff", "isActive": True, "passwordHash": pwd})

    return {"db": db, "tenant_id": tenant_id}


def _login(client: TestClient, email: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secret12345"},
        headers={"Origin": settings.frontend_origins[0]},
    )
    return res.json()["data"]["accessToken"]


def _assert_error_envelope(body: dict, expected_code: str):
    assert body["success"] is False
    assert body["data"] is None
    assert isinstance(body["error"], dict)
    assert body["error"]["code"] == expected_code
    assert isinstance(body["error"]["message"], str)
    assert len(body["error"]["message"]) > 0


def test_envelope_401_no_token():
    with TestClient(app) as client:
        res = client.get("/api/v1/vehicles")
        assert res.status_code == 401
        _assert_error_envelope(res.json(), "UNAUTHORIZED")


def test_envelope_403_wrong_role():
    with TestClient(app) as client:
        staff_token = _login(client, "staff@example.com")
        res = client.post(
            "/api/v1/vehicles",
            data={"makeModel": "Test", "registration": "GJ 01 AA 1111", "dailyRate": 500},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert res.status_code == 403
        _assert_error_envelope(res.json(), "FORBIDDEN")


def test_envelope_404_not_found():
    with TestClient(app) as client:
        owner_token = _login(client, "owner@example.com")
        fake_id = str(ObjectId())
        res = client.get(f"/api/v1/vehicles/{fake_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert res.status_code == 404
        _assert_error_envelope(res.json(), "NOT_FOUND")


def test_envelope_422_validation_error():
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email"},  # missing password
        )
        assert res.status_code == 422
        body = res.json()
        _assert_error_envelope(body, "VALIDATION_ERROR")
        assert "details" in body["error"]
        details = body["error"]["details"]
        assert isinstance(details, list)
        assert len(details) >= 1
        assert any(d.get("field") == "password" and "Field required" in d.get("message", "") for d in details)


def test_envelope_500_unhandled_exception(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as client:
        owner_token = _login(client, "owner@example.com")

        # Force an unexpected internal error with sensitive text
        from app.modules.vehicles import router as vehicles_router

        def crash(*args, **kwargs):
            raise ZeroDivisionError("sensitive internal error: file c:/app/secret.py line 42")

        monkeypatch.setattr(vehicles_router, "_doc_to_response", crash)

        # Seed a vehicle so get_vehicle calls _doc_to_response
        db = mongodb.get_database()
        tenant = db.tenants.find_one()
        v_id = db.vehicles.insert_one({
            "name": "Crashing Car",
            "tenantId": tenant["_id"],
            "deletedAt": None,
        }).inserted_id

        res = client.get(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert res.status_code == 500

        body = res.json()
        _assert_error_envelope(body, "INTERNAL_ERROR")
        assert body["error"]["message"] == "An unexpected error occurred."

        # Verify no traceback, exception text, or file paths leaked into response body
        raw_text = res.text.lower()
        assert "traceback" not in raw_text
        assert "zerodivision" not in raw_text
        assert "secret.py" not in raw_text
        assert "c:/" not in raw_text

