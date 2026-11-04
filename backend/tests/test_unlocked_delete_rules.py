"""
Tests for Phase 3b:
1. Vehicle soft-delete guard (blocked by Pending, Confirmed, Active; allowed when Completed/Cancelled).
2. Customer soft-delete guard (blocked by Pending, Confirmed, Active; allowed when Completed/Cancelled).
3. Dynamic vehicle availability derivation on read (Maintenance -> Maintenance, Active -> Rented, else Available).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import mongomock
import mongomock.filtering
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

mongomock.filtering.TYPE_MAP["null"] = lambda v: v is None

from app.core.config import settings
from app.db import mongodb
from app.main import app
from app.modules.auth import deps as auth_deps
from app.modules.auth import router as auth_router
from app.modules.auth.service import hash_password
from app.modules.bookings import router as bookings_router
from app.modules.bookings import service as bookings_service
from app.modules.customers import router as customers_router
from app.modules.vehicles import router as vehicles_router


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-must-be-at-least-32-bytes-long!")
    monkeypatch.setattr(settings, "mongodb_uri", "mongodb://mock")
    monkeypatch.setattr(settings, "app_env", "testing")
    monkeypatch.setattr(settings, "booking_grace_period_days", 1)

    with auth_router._attempt_lock:
        auth_router._attempts.clear()

    client = mongomock.MongoClient(tz_aware=True)
    db = client[settings.mongodb_database]

    monkeypatch.setattr(mongodb, "get_database", lambda c=None: db)
    monkeypatch.setattr(mongodb, "create_mongo_client", lambda: client)
    monkeypatch.setattr(auth_deps, "get_database", lambda c=None: db)
    monkeypatch.setattr(auth_router, "get_database", lambda c=None: db)
    monkeypatch.setattr(customers_router, "get_database", lambda c=None: db)
    monkeypatch.setattr(customers_router, "_get_customers_col", lambda: db["customers"])
    monkeypatch.setattr(vehicles_router, "get_database", lambda c=None: db)
    monkeypatch.setattr(vehicles_router, "_get_vehicles_col", lambda: db["vehicles"])
    monkeypatch.setattr(vehicles_router, "_get_bookings_col", lambda: db["bookings"])
    monkeypatch.setattr(bookings_router, "get_database", lambda c=None: db)

    return db


@pytest.fixture
def env(mock_db, monkeypatch):
    pwd_hash = hash_password("SecretPassword123")
    tenant_id = mock_db.tenants.insert_one({"name": "Tenant A", "slug": "tenant-a", "status": "active"}).inserted_id

    mock_db.users.insert_many([
        {"email": "owner@a.com", "tenantId": tenant_id, "role": "owner", "passwordHash": pwd_hash, "isActive": True},
    ])

    test_client = TestClient(app)

    res = test_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@a.com", "password": "SecretPassword123"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert res.status_code == 200
    token = res.json()["data"]["accessToken"]

    now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(bookings_service, "_now_utc", lambda: now)

    v_id = mock_db.vehicles.insert_one({
        "tenantId": tenant_id,
        "name": "Royal Enfield Hunter",
        "registration": "KA 01 CD 5678",
        "registrationNumber": "KA01CD5678",
        "type": "Motorcycle",
        "status": "Online",
        "availability": "Available",
        "fleetAvailability": "Available",
        "dailyRate": 1500,
        "price": 1500,
        "securityDeposit": 3000,
        "bookingGuard": 0,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    c_id = mock_db.customers.insert_one({
        "tenantId": tenant_id,
        "name": "Neha Patel",
        "phone": "+919123456789",
        "email": "neha@example.com",
        "status": "Verified",
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    def create_booking(status_val="Pending"):
        res_b = test_client.post(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "customerId": str(c_id),
                "vehicleId": str(v_id),
                "startDate": (now + timedelta(days=1)).isoformat(),
                "endDate": (now + timedelta(days=3)).isoformat(),
                "pickupLocation": "HQ",
                "status": status_val,
            },
        )
        assert res_b.status_code == 201
        return res_b.json()["data"]["id"]

    return {
        "client": test_client,
        "db": mock_db,
        "tenant_id": tenant_id,
        "token": token,
        "vehicle_id": str(v_id),
        "customer_id": str(c_id),
        "create_booking": create_booking,
        "now": now,
    }


def test_vehicle_delete_blocked_by_active_confirmed_or_pending(env):
    client = env["client"]
    token = env["token"]
    v_id = env["vehicle_id"]

    # 1. Blocked by Pending booking
    b_id = env["create_booking"](status_val="Pending")
    del_res = client.delete(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 409
    assert "active or upcoming bookings" in del_res.text

    # Transition to Confirmed -> still blocked
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Confirmed"})
    del_res2 = client.delete(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res2.status_code == 409

    # Transition to Active -> still blocked
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Active"})
    del_res3 = client.delete(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res3.status_code == 409

    # Complete the booking -> delete now succeeds
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Completed"})
    del_res4 = client.delete(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res4.status_code == 200
    assert del_res4.json()["success"] is True


def test_customer_delete_blocked_by_active_confirmed_or_pending(env):
    client = env["client"]
    token = env["token"]
    c_id = env["customer_id"]

    # 1. Blocked by Pending
    b_id = env["create_booking"](status_val="Pending")
    del_res = client.delete(f"/api/v1/customers/{c_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 409
    assert "active or upcoming bookings" in del_res.text

    # 2. Blocked by Confirmed
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Confirmed"})
    del_res2 = client.delete(f"/api/v1/customers/{c_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res2.status_code == 409

    # 3. Cancelled booking -> customer delete succeeds
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Cancelled"})
    del_res3 = client.delete(f"/api/v1/customers/{c_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res3.status_code == 200
    assert del_res3.json()["success"] is True


def test_derived_vehicle_availability_on_read(env):
    client = env["client"]
    token = env["token"]
    v_id = env["vehicle_id"]
    db = env["db"]

    # Initially Available
    res = client.get(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["data"]["availability"] == "Available"

    # Create and activate a booking -> availability derived as Rented
    b_id = env["create_booking"](status_val="Confirmed")
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Active"})

    res_rented = client.get(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_rented.status_code == 200
    assert res_rented.json()["data"]["availability"] == "Rented"

    # Complete booking -> availability reverts to Available
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Completed"})
    res_avail = client.get(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_avail.status_code == 200
    assert res_avail.json()["data"]["availability"] == "Available"

    # Maintenance overrides even if no active booking
    db.vehicles.update_one({"_id": ObjectId(v_id)}, {"$set": {"availability": "Maintenance"}})
    res_maint = client.get(f"/api/v1/vehicles/{v_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_maint.status_code == 200
    assert res_maint.json()["data"]["availability"] == "Maintenance"

