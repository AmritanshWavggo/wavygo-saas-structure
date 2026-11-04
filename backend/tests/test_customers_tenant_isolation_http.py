"""
HTTP-level tenant isolation tests for the Customers API using FastAPI TestClient with mongomock.
"""

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
def mock_db(monkeypatch):
    import mongomock.filtering
    mongomock.filtering.TYPE_MAP["null"] = lambda v: v is None

    from app.modules.auth import deps as auth_deps
    from app.modules.auth import router as auth_router
    from app.modules.customers import router as customers_router

    monkeypatch.setattr(settings, "jwt_secret", "test-secret-must-be-at-least-32-bytes-long!")
    monkeypatch.setattr(settings, "mongodb_uri", "mongodb://mock")

    # Reset in-memory rate limiter
    with auth_router._attempt_lock:
        auth_router._attempts.clear()

    client = mongomock.MongoClient()
    db = client[settings.mongodb_database]

    monkeypatch.setattr(mongodb, "get_database", lambda c=None: db)
    monkeypatch.setattr(mongodb, "create_mongo_client", lambda: client)
    monkeypatch.setattr(auth_deps, "get_database", lambda c=None: db)
    monkeypatch.setattr(auth_router, "get_database", lambda c=None: db)
    monkeypatch.setattr(customers_router, "get_database", lambda c=None: db)

    return db


@pytest.fixture
def seeded_env(mock_db):
    pwd_hash = hash_password("SecretPassword123")
    tenant_a_id = mock_db.tenants.insert_one({"name": "Tenant A", "slug": "tenant-a", "status": "active"}).inserted_id
    tenant_b_id = mock_db.tenants.insert_one({"name": "Tenant B", "slug": "tenant-b", "status": "active"}).inserted_id

    users = [
        {"email": "owner@a.com", "tenantId": tenant_a_id, "role": "owner", "passwordHash": pwd_hash, "isActive": True},
        {"email": "manager@a.com", "tenantId": tenant_a_id, "role": "manager", "passwordHash": pwd_hash, "isActive": True},
        {"email": "staff@a.com", "tenantId": tenant_a_id, "role": "staff", "passwordHash": pwd_hash, "isActive": True},
        {"email": "owner@b.com", "tenantId": tenant_b_id, "role": "owner", "passwordHash": pwd_hash, "isActive": True},
        {"email": "manager@b.com", "tenantId": tenant_b_id, "role": "manager", "passwordHash": pwd_hash, "isActive": True},
        {"email": "staff@b.com", "tenantId": tenant_b_id, "role": "staff", "passwordHash": pwd_hash, "isActive": True},
    ]
    mock_db.users.insert_many(users)

    client = TestClient(app)

    def login(email: str) -> str:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecretPassword123"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        return res.json()["data"]["accessToken"]

    tokens = {u["email"]: login(u["email"]) for u in users}

    return {
        "client": client,
        "tokens": tokens,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "db": mock_db,
    }


def test_customers_tenant_isolation_http(seeded_env):
    client = seeded_env["client"]
    token_a_owner = seeded_env["tokens"]["owner@a.com"]
    token_a_staff = seeded_env["tokens"]["staff@a.com"]
    token_b_owner = seeded_env["tokens"]["owner@b.com"]

    # 1. Tenant B creates a canary customer
    res_b = client.post(
        "/api/v1/customers",
        json={
            "name": "Canary Customer B",
            "phone": "+919876543210",
            "email": "canary@b.com",
            "status": "Verified",
        },
        headers={"Authorization": f"Bearer {token_b_owner}"},
    )
    assert res_b.status_code == 201
    canary_b_id = res_b.json()["data"]["id"]

    # 2. Tenant A GET canary B -> 404
    res = client.get(
        f"/api/v1/customers/{canary_b_id}",
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert res.status_code == 404
    assert res.json()["success"] is False

    # 3. Tenant A PATCH canary B -> 404
    res = client.patch(
        f"/api/v1/customers/{canary_b_id}",
        json={"name": "Tampered Name"},
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert res.status_code == 404

    # 4. Tenant A DELETE canary B -> 404
    res = client.delete(
        f"/api/v1/customers/{canary_b_id}",
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert res.status_code == 404

    # Tenant B fetches its canary and verifies it is unchanged and not deleted
    res_b_verify = client.get(
        f"/api/v1/customers/{canary_b_id}",
        headers={"Authorization": f"Bearer {token_b_owner}"},
    )
    assert res_b_verify.status_code == 200
    canary_data = res_b_verify.json()["data"]
    assert canary_data["name"] == "Canary Customer B"
    assert canary_data["email"] == "canary@b.com"
    assert canary_data["status"] == "Verified"

    # 5. Tenant A's customer list never contains B's canary
    res = client.get(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert res.status_code == 200
    ids_in_a = [c["id"] for c in res.json()["data"]]
    assert canary_b_id not in ids_in_a

    # 6. Supplying tenantId in payload is rejected with 422 (extra="forbid")
    res = client.post(
        "/api/v1/customers",
        json={
            "name": "Spoofed Tenant Customer",
            "phone": "+919123456789",
            "tenantId": str(seeded_env["tenant_b_id"]),
        },
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert res.status_code == 422
    assert res.json()["success"] is False

    # 7. Unauthenticated GET, POST and DELETE return 401
    res_unauth_get = client.get("/api/v1/customers")
    assert res_unauth_get.status_code == 401
    assert res_unauth_get.json()["success"] is False

    res_unauth_post = client.post(
        "/api/v1/customers",
        json={"name": "No Auth", "phone": "+919999988888"},
    )
    assert res_unauth_post.status_code == 401
    assert res_unauth_post.json()["success"] is False

    res_unauth_del = client.delete(f"/api/v1/customers/{canary_b_id}")
    assert res_unauth_del.status_code == 401
    assert res_unauth_del.json()["success"] is False


def test_customers_role_permissions(seeded_env):
    client = seeded_env["client"]
    token_staff = seeded_env["tokens"]["staff@a.com"]
    token_manager = seeded_env["tokens"]["manager@a.com"]
    token_owner = seeded_env["tokens"]["owner@a.com"]

    # 1. Staff creates customer -> status is forced to "Review"
    res = client.post(
        "/api/v1/customers",
        json={"name": "Staff Customer", "phone": "+919988776655"},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res.status_code == 201
    customer_id = res.json()["data"]["id"]
    assert res.json()["data"]["status"] == "Review"

    # 2. Staff attempts to create with status "Verified" -> 403 Forbidden
    res_forbidden = client.post(
        "/api/v1/customers",
        json={"name": "Verified Staff Customer", "phone": "+919988776654", "status": "Verified"},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res_forbidden.status_code == 403

    # 3. Staff attempts to modify status to "Verified" via PATCH -> 403 Forbidden
    res_patch_forbidden = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"status": "Verified"},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res_patch_forbidden.status_code == 403

    # Staff sends customer's current status ("Review") -> 200 OK
    res_patch_same_status = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"status": "Review"},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res_patch_same_status.status_code == 200
    assert res_patch_same_status.json()["data"]["status"] == "Review"

    # 4. Staff can update non-status fields (e.g. notes, name)
    res_patch_ok = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"notes": "Updated by staff", "name": "Staff Customer Renamed"},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res_patch_ok.status_code == 200
    assert res_patch_ok.json()["data"]["notes"] == "Updated by staff"
    assert res_patch_ok.json()["data"]["name"] == "Staff Customer Renamed"

    # 5. Staff attempts to DELETE -> 403 Forbidden
    res_del_forbidden = client.delete(
        f"/api/v1/customers/{customer_id}",
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res_del_forbidden.status_code == 403

    # 6. Manager modifies status to "Verified" -> 200 OK
    res_mgr_status = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"status": "Verified"},
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert res_mgr_status.status_code == 200
    assert res_mgr_status.json()["data"]["status"] == "Verified"

    # 7. Manager can delete customer -> 200 OK
    res_mgr_del = client.delete(
        f"/api/v1/customers/{customer_id}",
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert res_mgr_del.status_code == 200
    assert res_mgr_del.json()["data"]["deleted"] is True

    # 8. Owner creates and deletes another customer -> 200 OK
    res_owner_create = client.post(
        "/api/v1/customers",
        json={"name": "Owner Customer", "phone": "+919988776653", "status": "Verified"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert res_owner_create.status_code == 201
    owner_cust_id = res_owner_create.json()["data"]["id"]

    res_owner_del = client.delete(
        f"/api/v1/customers/{owner_cust_id}",
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert res_owner_del.status_code == 200

