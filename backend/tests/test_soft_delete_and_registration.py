from __future__ import annotations

import mongomock
import mongomock.filtering
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import mongodb
from app.main import app
from app.modules.auth.service import hash_password
from app.services import cloudinary_service
from app.services.rc_service import check_rc_duplicate


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """
    Configure mongomock for soft delete and plate re-registration tests.

    Note on mongomock and partial unique indexes:
    Standard mongomock does not implement $type: "null" out-of-the-box in TYPE_MAP.
    Even with TYPE_MAP["null"] patched, mongomock's index checking during collection
    updates/inserts can vary in how strictly it evaluates partialFilterExpressions.
    We test both the HTTP endpoint layer (soft-delete, then re-register same plate in
    the same tenant, as well as same plate in another tenant) and the underlying
    check_rc_duplicate service logic which explicitly scopes to deletedAt: None.
    """
    mongomock.filtering.TYPE_MAP["null"] = lambda v: v is None

    from app.modules.auth import deps as auth_deps
    from app.modules.auth import router as auth_router
    from app.modules.vehicles import router as vehicles_router

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
    monkeypatch.setattr(vehicles_router, "get_database", lambda c=None: db)

    monkeypatch.setattr(
        cloudinary_service,
        "upload_file",
        lambda *args, **kwargs: {"url": "https://cdn.example.com/asset.jpg", "public_id": "asset_123"},
    )
    monkeypatch.setattr(
        cloudinary_service,
        "delete_file",
        lambda *args, **kwargs: {"result": "ok"},
    )
    monkeypatch.setattr(
        vehicles_router.cloudinary_service,
        "upload_file",
        lambda *args, **kwargs: {"url": "https://cdn.example.com/asset.jpg", "public_id": "asset_123"},
    )
    monkeypatch.setattr(
        vehicles_router.cloudinary_service,
        "delete_file",
        lambda *args, **kwargs: {"result": "ok"},
    )

    return db


@pytest.fixture
def tenants_and_owners(mock_db):
    pwd_hash = hash_password("SecretPassword123")
    tenant_a_id = mock_db.tenants.insert_one({"name": "Tenant A", "slug": "tenant-a", "status": "active"}).inserted_id
    tenant_b_id = mock_db.tenants.insert_one({"name": "Tenant B", "slug": "tenant-b", "status": "active"}).inserted_id

    user_a = mock_db.users.insert_one({
        "tenantId": tenant_a_id,
        "email": "owner_a@example.com",
        "role": "owner",
        "isActive": True,
        "passwordHash": pwd_hash,
    }).inserted_id

    user_b = mock_db.users.insert_one({
        "tenantId": tenant_b_id,
        "email": "owner_b@example.com",
        "role": "owner",
        "isActive": True,
        "passwordHash": pwd_hash,
    }).inserted_id

    return {
        "db": mock_db,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "user_a": user_a,
        "user_b": user_b,
    }


def login_token(client: TestClient, email: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecretPassword123"},
        headers={"Origin": settings.frontend_origins[0]},
    )
    assert res.status_code == 200
    return res.json()["data"]["accessToken"]


def test_soft_delete_and_plate_reregistration_http(tenants_and_owners):
    """
    Test over HTTP:
    1. Register plate in Tenant A.
    2. Soft-delete vehicle in Tenant A.
    3. Re-register the SAME plate in Tenant A -> succeeds.
    4. Register the SAME plate in Tenant B -> succeeds.
    """
    with TestClient(app) as client:
        token_a = login_token(client, "owner_a@example.com")
        token_b = login_token(client, "owner_b@example.com")
        headers_a = {"Authorization": f"Bearer {token_a}", "Origin": settings.frontend_origins[0]}
        headers_b = {"Authorization": f"Bearer {token_b}", "Origin": settings.frontend_origins[0]}

        plate = "GJ05AB8888"
        payload_a = {
            "makeModel": "Honda Activa A1",
            "registration": "GJ 05 AB 8888",
            "registrationNumber": plate,
            "year": 2024,
            "type": "Scooter",
            "fuel": "Petrol",
            "transmission": "Automatic",
            "dailyRate": 500.0,
            "pickupAddress": "Surat",
        }

        # 1. Create initial vehicle in Tenant A
        res_create_1 = client.post("/api/v1/vehicles", data=payload_a, headers=headers_a)
        assert res_create_1.status_code == 201
        vehicle_1_id = res_create_1.json()["data"]["id"]

        # Duplicate before soft-delete must fail with 409
        res_duplicate = client.post("/api/v1/vehicles", data=payload_a, headers=headers_a)
        assert res_duplicate.status_code == 409

        # 2. Soft-delete vehicle in Tenant A
        res_del = client.delete(f"/api/v1/vehicles/{vehicle_1_id}", headers=headers_a)
        assert res_del.status_code == 200

        # Verify it has deletedAt set in DB
        db = tenants_and_owners["db"]
        doc_1 = db.vehicles.find_one({"_id": ObjectId(vehicle_1_id)})
        assert doc_1["deletedAt"] is not None

        # 3. Re-register the SAME plate in Tenant A -> succeeds!
        payload_a2 = dict(payload_a, makeModel="Honda Activa A2")
        res_create_2 = client.post("/api/v1/vehicles", data=payload_a2, headers=headers_a)
        assert res_create_2.status_code == 201, f"Re-registration failed: {res_create_2.text}"
        vehicle_2_id = res_create_2.json()["data"]["id"]
        assert vehicle_2_id != vehicle_1_id

        # 4. Same plate in Tenant B -> succeeds!
        payload_b = {
            "makeModel": "Honda Activa B",
            "registration": "GJ 05 AB 8888",
            "registrationNumber": plate,
            "year": 2024,
            "type": "Scooter",
            "fuel": "Petrol",
            "transmission": "Automatic",
            "dailyRate": 550.0,
            "pickupAddress": "Ahmedabad",
        }
        res_create_b = client.post("/api/v1/vehicles", data=payload_b, headers=headers_b)
        assert res_create_b.status_code == 201, f"Tenant B registration failed: {res_create_b.text}"


def test_rc_duplicate_logic_excludes_soft_deleted_and_cross_tenant(tenants_and_owners):
    """
    Direct test of check_rc_duplicate service logic.
    Confirms duplicate check returns False for soft-deleted vehicles and vehicles in other tenants.
    """
    db = tenants_and_owners["db"]
    col = db.vehicles
    tenant_a = tenants_and_owners["tenant_a_id"]
    tenant_b = tenants_and_owners["tenant_b_id"]

    plate = "GJ05CD9999"

    # Active vehicle in tenant A
    v1_id = col.insert_one({"registrationNumber": plate, "tenantId": tenant_a, "deletedAt": None}).inserted_id
    assert check_rc_duplicate(plate, col, tenant_a) is True
    # Different tenant does not see duplicate
    assert check_rc_duplicate(plate, col, tenant_b) is False

    # Soft delete in tenant A
    col.update_one({"_id": v1_id}, {"$set": {"deletedAt": "2026-11-03T12:00:00Z"}})
    # Now tenant A does not see duplicate
    assert check_rc_duplicate(plate, col, tenant_a) is False

