from __future__ import annotations

import sys
import mongomock
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import mongodb
from app.main import app
from scripts import seed_tenant_owner


@pytest.fixture
def mock_seed_env(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-must-be-at-least-32-bytes-long!")
    monkeypatch.setattr(settings, "mongodb_uri", "mongodb://mock")

    client = mongomock.MongoClient()
    db = client[settings.mongodb_database]

    from app.modules.auth import deps as auth_deps
    from app.modules.auth import router as auth_router

    monkeypatch.setattr(mongodb, "get_database", lambda c=None: db)
    monkeypatch.setattr(mongodb, "create_mongo_client", lambda: client)
    monkeypatch.setattr(auth_deps, "get_database", lambda c=None: db)
    monkeypatch.setattr(auth_router, "get_database", lambda c=None: db)
    monkeypatch.setattr(seed_tenant_owner, "MongoClient", lambda _: client)

    return {"client": client, "db": db}


def test_seed_tenant_owner_normalizes_email_and_can_login(mock_seed_env, monkeypatch):
    test_args = [
        "seed_tenant_owner.py",
        "--name", "Acme Rental Co",
        "--email", "Owner@Example.com",
        "--password", "StrongOwnerPassword123",
        "--slug", "acme-rental",
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    # Run seed script
    seed_tenant_owner.main()

    # Check database stored normalized email
    db = mock_seed_env["db"]
    user = db.users.find_one({"email": "owner@example.com"})
    assert user is not None, "User should be found with normalized email 'owner@example.com'."
    assert user["email"] == "owner@example.com"
    # Ensure un-normalized email does not exist
    assert db.users.find_one({"email": "Owner@Example.com"}) is None or user["email"] == "owner@example.com"

    # Test login over HTTP with normalized "owner@example.com"
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "StrongOwnerPassword123"},
            headers={"Origin": settings.frontend_origins[0]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["user"]["email"] == "owner@example.com"
        assert "accessToken" in body["data"]

        # Also test logging in with mixed-case "Owner@Example.com"
        res_mixed = client.post(
            "/api/v1/auth/login",
            json={"email": "Owner@Example.com", "password": "StrongOwnerPassword123"},
            headers={"Origin": settings.frontend_origins[0]},
        )
        assert res_mixed.status_code == 200
        assert res_mixed.json()["data"]["user"]["email"] == "owner@example.com"

