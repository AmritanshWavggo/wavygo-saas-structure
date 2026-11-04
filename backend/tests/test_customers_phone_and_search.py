"""
Unit and integration tests for customer phone rules, duplicate detection,
soft deletion, search escaping, pagination, metrics, and name validation.

NOTE: mongomock does not enforce MongoDB unique partial indexes (such as
uq_customer_tenant_phone_active). Phone duplicate prevention and soft-delete
re-registration are enforced through service/router-level tenant query checks
and DuplicateKeyError trapping for production MongoDB.
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
def env(mock_db):
    pwd_hash = hash_password("SecretPassword123")
    tenant_a_id = mock_db.tenants.insert_one({"name": "Tenant A", "slug": "tenant-a", "status": "active"}).inserted_id
    tenant_b_id = mock_db.tenants.insert_one({"name": "Tenant B", "slug": "tenant-b", "status": "active"}).inserted_id

    mock_db.users.insert_one({"email": "owner@a.com", "tenantId": tenant_a_id, "role": "owner", "passwordHash": pwd_hash, "isActive": True})
    mock_db.users.insert_one({"email": "owner@b.com", "tenantId": tenant_b_id, "role": "owner", "passwordHash": pwd_hash, "isActive": True})

    client = TestClient(app)

    def login(email: str) -> str:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecretPassword123"},
            headers={"Origin": "http://localhost:5173"},
        )
        return res.json()["data"]["accessToken"]

    token_a = login("owner@a.com")
    token_b = login("owner@b.com")

    return {
        "client": client,
        "token_a": token_a,
        "token_b": token_b,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
    }


def test_phone_normalization_and_validation(env):
    client = env["client"]
    token = env["token_a"]

    # 1. 10 digits starting 6-9 becomes +91XXXXXXXXXX
    res = client.post(
        "/api/v1/customers",
        json={"name": "Pooja Sharma", "phone": "9876543210"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["data"]["phone"] == "+919876543210"

    # Formatted 10 digits with spaces/hyphens
    res2 = client.post(
        "/api/v1/customers",
        json={"name": "Rajesh Kumar", "phone": "7890 12-3456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 201
    assert res2.json()["data"]["phone"] == "+917890123456"

    # 2. Leading + with 8-15 digits is accepted
    res3 = client.post(
        "/api/v1/customers",
        json={"name": "International Client", "phone": "+14155552671"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res3.status_code == 201
    assert res3.json()["data"]["phone"] == "+14155552671"

    # 3. 10 digits starting with 1-5 is rejected with 422
    res_bad_start = client.post(
        "/api/v1/customers",
        json={"name": "Bad Start", "phone": "5123456789"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_bad_start.status_code == 422
    assert res_bad_start.json()["success"] is False

    # 4. Leading + with < 8 digits is rejected with 422
    res_too_short = client.post(
        "/api/v1/customers",
        json={"name": "Too Short", "phone": "+1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_too_short.status_code == 422

    # 5. Leading + with > 15 digits is rejected with 422
    res_too_long = client.post(
        "/api/v1/customers",
        json={"name": "Too Long", "phone": "+12345678901234567"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_too_long.status_code == 422


def test_duplicate_phone_and_soft_delete_re_registration(env):
    """
    Asserts 409 CONFLICT on duplicate phone within tenant.
    Asserts cross-tenant phone sharing is allowed.
    Asserts soft-deleting a customer frees the phone for re-registration.
    """
    client = env["client"]
    token_a = env["token_a"]
    token_b = env["token_b"]

    # 1. Register customer in Tenant A
    res = client.post(
        "/api/v1/customers",
        json={"name": "Customer One", "phone": "+919876500000"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 201
    cust_id = res.json()["data"]["id"]

    # 2. Duplicate phone in Tenant A returns 409 CONFLICT
    res_dup = client.post(
        "/api/v1/customers",
        json={"name": "Customer Duplicate", "phone": "+919876500000"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["error"]["code"] == "CONFLICT"

    # 3. Same phone in Tenant B succeeds (tenant isolation)
    res_tenant_b = client.post(
        "/api/v1/customers",
        json={"name": "Tenant B Customer", "phone": "+919876500000"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_tenant_b.status_code == 201

    # 4. Soft-delete customer in Tenant A
    res_del = client.delete(
        f"/api/v1/customers/{cust_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_del.status_code == 200

    # 5. Re-registering the same phone in Tenant A now succeeds
    res_re_register = client.post(
        "/api/v1/customers",
        json={"name": "Re-registered Customer", "phone": "+919876500000"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_re_register.status_code == 201
    assert res_re_register.json()["data"]["name"] == "Re-registered Customer"


def test_search_escaping_and_phone_search(env):
    client = env["client"]
    token = env["token_a"]

    # Seed 2 customers
    client.post(
        "/api/v1/customers",
        json={"name": "Aarav Mehta", "phone": "+919876511111", "email": "aarav@test.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/v1/customers",
        json={"name": "Isha Patel", "phone": "+919876522222", "email": "isha@test.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # 1. Searching ".*" should NOT match everything (it must be escaped)
    res_regex = client.get(
        "/api/v1/customers?search=.*",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_regex.status_code == 200
    assert len(res_regex.json()["data"]) == 0

    # 2. Search by name substring
    res_name = client.get(
        "/api/v1/customers?search=aarav",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_name.status_code == 200
    assert len(res_name.json()["data"]) == 1
    assert res_name.json()["data"][0]["name"] == "Aarav Mehta"

    # 3. Search by normalized phone digits
    res_phone = client.get(
        "/api/v1/customers?search=98765 22222",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_phone.status_code == 200
    assert len(res_phone.json()["data"]) == 1
    assert res_phone.json()["data"][0]["name"] == "Isha Patel"


def test_pagination_and_metrics_declaration(env):
    client = env["client"]
    token = env["token_a"]

    # Seed customers
    for i in range(5):
        client.post(
            "/api/v1/customers",
            json={"name": f"Cust {i}", "phone": f"+91987653333{i}", "status": "Verified" if i < 3 else "Review"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # 1. Verify GET /metrics is NOT shadowed by GET /{id}
    res_metrics = client.get(
        "/api/v1/customers/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()["data"]
    assert metrics["totalCustomers"] == 5
    assert metrics["verifiedProfiles"] == 3
    # Requirement 3: totalCollected and pendingDues return null
    assert metrics["totalCollected"] is None
    assert metrics["pendingDues"] is None

    # 2. Pagination test
    res_p1 = client.get(
        "/api/v1/customers?page=1&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_p1.status_code == 200
    assert len(res_p1.json()["data"]) == 2
    assert res_p1.json()["meta"] == {"total": 5, "page": 1, "limit": 2}

    # 3. Null values on bookings / active / paid / pending
    cust = res_p1.json()["data"][0]
    assert cust["bookings"] is None
    assert cust["active"] is None
    assert cust["paid"] is None
    assert cust["pending"] is None


def test_patch_exclude_unset_and_name_validation(env):
    client = env["client"]
    token = env["token_a"]

    # Create customer with email
    res = client.post(
        "/api/v1/customers",
        json={"name": "Rohit Verma", "phone": "+919876544444", "email": "rohit@test.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cust_id = res.json()["data"]["id"]

    # 1. Clear email using null in PATCH
    res_patch_clear = client.patch(
        f"/api/v1/customers/{cust_id}",
        json={"email": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_patch_clear.status_code == 200
    assert res_patch_clear.json()["data"]["email"] is None

    # 2. Reject control characters in name
    res_bad_name = client.patch(
        f"/api/v1/customers/{cust_id}",
        json={"name": "Rohit\nVerma"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_bad_name.status_code == 422

    # 3. Reject control characters in email
    res_bad_email = client.patch(
        f"/api/v1/customers/{cust_id}",
        json={"email": "rohit\x00@test.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_bad_email.status_code == 422

