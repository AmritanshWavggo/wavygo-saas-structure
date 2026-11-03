from __future__ import annotations

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import mongodb
from app.main import app
from app.modules.auth.service import hash_password
from app.services import cloudinary_service


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    import mongomock.filtering
    mongomock.filtering.TYPE_MAP["null"] = lambda v: v is None

    from app.modules.auth import deps as auth_deps
    from app.modules.auth import router as auth_router
    from app.modules.vehicles import router as vehicles_router

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
    monkeypatch.setattr(vehicles_router, "get_database", lambda c=None: db)

    # Stub Cloudinary
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
def seeded_env(mock_db):
    pwd_hash = hash_password("SecretPassword123")
    tenant_a_id = mock_db.tenants.insert_one({"name": "Tenant A", "slug": "tenant-a", "status": "active"}).inserted_id
    tenant_b_id = mock_db.tenants.insert_one({"name": "Tenant B", "slug": "tenant-b", "status": "active"}).inserted_id

    users_data = [
        {"tenantId": tenant_a_id, "email": "owner_a@example.com", "role": "owner", "isActive": True, "passwordHash": pwd_hash},
        {"tenantId": tenant_a_id, "email": "manager_a@example.com", "role": "manager", "isActive": True, "passwordHash": pwd_hash},
        {"tenantId": tenant_a_id, "email": "staff_a@example.com", "role": "staff", "isActive": True, "passwordHash": pwd_hash},
        {"tenantId": tenant_b_id, "email": "owner_b@example.com", "role": "owner", "isActive": True, "passwordHash": pwd_hash},
        {"tenantId": tenant_b_id, "email": "manager_b@example.com", "role": "manager", "isActive": True, "passwordHash": pwd_hash},
        {"tenantId": tenant_b_id, "email": "staff_b@example.com", "role": "staff", "isActive": True, "passwordHash": pwd_hash},
    ]
    for u in users_data:
        u["_id"] = mock_db.users.insert_one(u).inserted_id

    # Canary vehicle belonging to Tenant B
    canary_id = mock_db.vehicles.insert_one({
        "name": "Canary Scooter B",
        "registration": "GJ 01 BB 9999",
        "registrationNumber": "GJ01BB9999",
        "year": 2024,
        "type": "Scooter",
        "fuel": "Petrol",
        "transmission": "Automatic",
        "dailyRate": 600.0,
        "price": 600.0,
        "minimumDays": 1,
        "securityDeposit": 500.0,
        "pickupLocation": {"address": "Ahmedabad"},
        "showOnWavygo": True,
        "status": "Online",
        "fleetAvailability": "Available",
        "tenantId": tenant_b_id,
        "createdBy": users_data[3]["_id"],
        "deletedAt": None,
        "photos": [],
        "documents": [],
    }).inserted_id

    return {
        "db": mock_db,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "canary_id": str(canary_id),
        "users": {u["email"]: u for u in users_data},
    }


def get_token(client: TestClient, email: str, password: str = "SecretPassword123") -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": settings.frontend_origins[0]},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["data"]["accessToken"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Origin": settings.frontend_origins[0]}


def sample_vehicle_form(**overrides) -> dict:
    data = {
        "makeModel": "Activa 6G",
        "registration": "GJ 05 AA 1111",
        "registrationNumber": "GJ05AA1111",
        "year": 2023,
        "type": "Scooter",
        "fuel": "Petrol",
        "transmission": "Automatic",
        "dailyRate": 450.0,
        "pickupAddress": "Surat Station",
    }
    data.update(overrides)
    return data


def test_tenant_a_gets_404_on_tenant_b_vehicle(seeded_env):
    with TestClient(app) as client:
        token_a_owner = get_token(client, "owner_a@example.com")
        headers_a = auth_headers(token_a_owner)
        canary_id = seeded_env["canary_id"]

        # GET
        res_get = client.get(f"/api/v1/vehicles/{canary_id}", headers=headers_a)
        assert res_get.status_code == 404
        assert res_get.json()["success"] is False

        # PATCH
        res_patch = client.patch(f"/api/v1/vehicles/{canary_id}", data={"dailyRate": "700"}, headers=headers_a)
        assert res_patch.status_code == 404
        assert res_patch.json()["success"] is False

        # Toggle show-on-wavygo
        res_toggle = client.patch(
            f"/api/v1/vehicles/{canary_id}/show-on-wavygo",
            json={"showOnWavygo": False},
            headers=headers_a,
        )
        assert res_toggle.status_code == 404
        assert res_toggle.json()["success"] is False

        # DELETE
        res_del = client.delete(f"/api/v1/vehicles/{canary_id}", headers=headers_a)
        assert res_del.status_code == 404
        assert res_del.json()["success"] is False


def test_tenant_a_vehicle_list_never_contains_tenant_b_canary(seeded_env):
    with TestClient(app) as client:
        token_a_owner = get_token(client, "owner_a@example.com")
        headers_a = auth_headers(token_a_owner)

        # Create one vehicle for Tenant A
        res_create = client.post("/api/v1/vehicles", data=sample_vehicle_form(), headers=headers_a)
        assert res_create.status_code == 201
        vehicle_a_id = res_create.json()["data"]["id"]

        # List vehicles for Tenant A
        res_list = client.get("/api/v1/vehicles", headers=headers_a)
        assert res_list.status_code == 200
        items = res_list.json()["data"]
        item_ids = [item["id"] for item in items]

        assert vehicle_a_id in item_ids
        assert seeded_env["canary_id"] not in item_ids


def test_tenant_id_in_payload_is_ignored_or_rejected_and_owned_by_token_tenant(seeded_env):
    with TestClient(app) as client:
        token_a_owner = get_token(client, "owner_a@example.com")
        headers_a = auth_headers(token_a_owner)

        # Attempt to inject tenantId pointing to Tenant B
        form_data = sample_vehicle_form(
            registrationNumber="GJ05AA2222",
            registration="GJ 05 AA 2222",
            tenantId=str(seeded_env["tenant_b_id"]),
        )
        res = client.post("/api/v1/vehicles", data=form_data, headers=headers_a)
        # Endpoint either rejects (422) or ignores extra form field and sets token's tenant
        if res.status_code == 201:
            created_id = res.json()["data"]["id"]
            db_doc = seeded_env["db"].vehicles.find_one({"_id": ObjectId(created_id)})
            assert db_doc["tenantId"] == seeded_env["tenant_a_id"]
            assert db_doc["tenantId"] != seeded_env["tenant_b_id"]
        else:
            assert res.status_code == 422


def test_role_permissions_staff_manager_owner(seeded_env):
    with TestClient(app) as client:
        token_owner = get_token(client, "owner_a@example.com")
        token_manager = get_token(client, "manager_a@example.com")
        token_staff = get_token(client, "staff_a@example.com")

        # Staff cannot create
        form_staff = sample_vehicle_form(registrationNumber="GJ05AA3333", registration="GJ 05 AA 3333")
        res_staff_create = client.post("/api/v1/vehicles", data=form_staff, headers=auth_headers(token_staff))
        assert res_staff_create.status_code == 403

        # Manager CAN create
        form_mgr = sample_vehicle_form(registrationNumber="GJ05AA4444", registration="GJ 05 AA 4444")
        res_mgr_create = client.post("/api/v1/vehicles", data=form_mgr, headers=auth_headers(token_manager))
        assert res_mgr_create.status_code == 201
        vehicle_id = res_mgr_create.json()["data"]["id"]

        # Manager CANNOT delete
        res_mgr_del = client.delete(f"/api/v1/vehicles/{vehicle_id}", headers=auth_headers(token_manager))
        assert res_mgr_del.status_code == 403

        # Owner CAN delete
        res_owner_del = client.delete(f"/api/v1/vehicles/{vehicle_id}", headers=auth_headers(token_owner))
        assert res_owner_del.status_code == 200


def test_no_token_returns_401():
    with TestClient(app) as client:
        res = client.get("/api/v1/vehicles")
        assert res.status_code == 401
        assert res.json()["success"] is False
        assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_deactivated_user_valid_token_is_rejected(seeded_env):
    with TestClient(app) as client:
        token_owner = get_token(client, "owner_a@example.com")
        headers = auth_headers(token_owner)

        # Before deactivation, request works
        res_before = client.get("/api/v1/vehicles", headers=headers)
        assert res_before.status_code == 200

        # Deactivate user in database
        seeded_env["db"].users.update_one({"email": "owner_a@example.com"}, {"$set": {"isActive": False}})

        # Same valid token must now be rejected
        res_after = client.get("/api/v1/vehicles", headers=headers)
        assert res_after.status_code == 401
        assert res_after.json()["success"] is False
