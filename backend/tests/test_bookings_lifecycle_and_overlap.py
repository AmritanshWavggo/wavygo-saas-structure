"""
Unit and integration tests for Bookings module (Phase 3a).
Each test function isolates a single specification requirement.
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
from app.modules.bookings.counters import generate_booking_number
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.service import (
    BookingTransactionTimeoutError,
    calculate_billable_days,
    float_to_paise,
)
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
    monkeypatch.setattr(vehicles_router, "get_database", lambda c=None: db)
    monkeypatch.setattr(vehicles_router, "_get_vehicles_col", lambda: db["vehicles"])
    monkeypatch.setattr(vehicles_router, "_get_bookings_col", lambda: db["bookings"])
    monkeypatch.setattr(bookings_router, "get_database", lambda c=None: db)

    return db


@pytest.fixture
def env(mock_db):
    pwd_hash = hash_password("SecretPassword123")
    tenant_a_id = mock_db.tenants.insert_one({"name": "Tenant A", "slug": "tenant-a", "status": "active"}).inserted_id
    tenant_b_id = mock_db.tenants.insert_one({"name": "Tenant B", "slug": "tenant-b", "status": "active"}).inserted_id

    mock_db.users.insert_many([
        {"email": "owner@a.com", "tenantId": tenant_a_id, "role": "owner", "passwordHash": pwd_hash, "isActive": True},
        {"email": "manager@a.com", "tenantId": tenant_a_id, "role": "manager", "passwordHash": pwd_hash, "isActive": True},
        {"email": "staff@a.com", "tenantId": tenant_a_id, "role": "staff", "passwordHash": pwd_hash, "isActive": True},
        {"email": "owner@b.com", "tenantId": tenant_b_id, "role": "owner", "passwordHash": pwd_hash, "isActive": True},
    ])

    test_client = TestClient(app)

    def get_token(email: str) -> str:
        res = test_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecretPassword123"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert res.status_code == 200, res.text
        return res.json()["data"]["accessToken"]

    token_a = get_token("owner@a.com")
    token_manager_a = get_token("manager@a.com")
    token_staff_a = get_token("staff@a.com")
    token_b = get_token("owner@b.com")

    now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
    v_a_id = mock_db.vehicles.insert_one({
        "tenantId": tenant_a_id,
        "name": "Hyundai Creta",
        "registration": "KA 01 AB 1234",
        "registrationNumber": "KA01AB1234",
        "type": "Motorcycle",
        "status": "Online",
        "availability": "Available",
        "dailyRate": 2500,
        "price": 2500,
        "securityDeposit": 5000,
        "bookingGuard": 0,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    c_a_id = mock_db.customers.insert_one({
        "tenantId": tenant_a_id,
        "name": "Aarav Sharma",
        "phone": "+919876543210",
        "email": "aarav@example.com",
        "status": "Verified",
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    v_b_id = mock_db.vehicles.insert_one({
        "tenantId": tenant_b_id,
        "name": "Mahindra Thar",
        "registration": "DL 02 CD 5678",
        "registrationNumber": "DL02CD5678",
        "type": "Scooter",
        "status": "Online",
        "availability": "Available",
        "dailyRate": 3500,
        "price": 3500,
        "securityDeposit": 8000,
        "bookingGuard": 0,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    c_b_id = mock_db.customers.insert_one({
        "tenantId": tenant_b_id,
        "name": "Rohan Gupta",
        "phone": "+919811122233",
        "email": "rohan@example.com",
        "status": "Verified",
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    return {
        "client": test_client,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "token_a": token_a,
        "token_manager_a": token_manager_a,
        "token_staff_a": token_staff_a,
        "token_b": token_b,
        "vehicle_a_id": str(v_a_id),
        "customer_a_id": str(c_a_id),
        "vehicle_b_id": str(v_b_id),
        "customer_b_id": str(c_b_id),
        "vehicle_a_oid": v_a_id,
        "customer_a_oid": c_a_id,
        "vehicle_b_oid": v_b_id,
        "customer_b_oid": c_b_id,
        "now": now,
    }


# ===========================================================================
# 1. Datetime Timezone Awareness and HTTP Validation Tests
# ===========================================================================
def test_stored_then_read_datetime_is_tz_aware(mock_db):
    dt = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    mock_db.bookings.insert_one({"startDate": dt, "testKey": "tz_test"})
    doc = mock_db.bookings.find_one({"testKey": "tz_test"})
    assert doc is not None
    assert doc["startDate"].tzinfo is not None, "Stored datetime must be timezone-aware when read"


def test_reject_naive_datetime_http_post(env):
    client = env["client"]
    token = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00",  # naive
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Airport Terminal 1",
        },
    )
    assert res.status_code == 422
    assert "timezone offset" in res.text


def test_reject_naive_datetime_http_get_availability(env):
    client = env["client"]
    token = env["token_a"]

    res = client.get(
        "/api/v1/bookings/availability",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00",  # naive
            "endDate": "2026-12-12T10:00:00Z",
        },
    )
    assert res.status_code == 422
    assert "timezone offset" in res.text


def test_reject_tenant_id_in_booking_create_body(env):
    client = env["client"]
    token = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Airport Terminal 1",
            "tenantId": str(ObjectId()),
        },
    )
    assert res.status_code == 422
    assert "extra_forbidden" in res.text or "Extra inputs are not permitted" in res.text


def test_reject_start_date_greater_or_equal_end_date(env):
    client = env["client"]
    token = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-15T10:00:00Z",
            "endDate": "2026-12-15T10:00:00Z",
            "pickupLocation": "Airport Terminal 1",
        },
    )
    assert res.status_code == 422
    assert "strictly after" in res.text


def test_duration_exactly_90_days_accepted(env):
    client = env["client"]
    token = env["token_a"]

    start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=90)

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 201
    assert res.json()["data"]["billableDays"] == 90


def test_duration_90_days_plus_one_second_rejected(env):
    client = env["client"]
    token = env["token_a"]

    start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=90, seconds=1)

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 422
    assert "cannot exceed 90 days" in res.text


# Frozen clock for deterministic grace window tests (midnight safe in IST)
FROZEN_CLOCK = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)


def test_start_just_inside_grace_window_accepted(env, monkeypatch):
    client = env["client"]
    token = env["token_a"]

    # Injected clock = 2026-11-10T12:00:00Z (17:30 IST on Nov 10).
    # Grace window: 1 day -> 00:00 IST of Nov 9 = 2026-11-08T18:30:00Z.
    # 2026-11-08T18:30:00Z is just inside the grace boundary -> 201 accepted.
    monkeypatch.setattr(bookings_service, "_now_utc", lambda: FROZEN_CLOCK)

    start = datetime(2026, 11, 8, 18, 30, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=2)

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 201


def test_start_just_outside_grace_window_rejected(env, monkeypatch):
    client = env["client"]
    token = env["token_a"]

    # 2026-11-08T18:29:59Z is 1 second before the 18:30:00Z boundary -> rejected (422).
    monkeypatch.setattr(bookings_service, "_now_utc", lambda: FROZEN_CLOCK)

    start = datetime(2026, 11, 8, 18, 29, 59, tzinfo=timezone.utc)
    end = start + timedelta(days=2)

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 422
    assert "grace window" in res.text


def test_grace_window_advances_at_midnight_ist(env, monkeypatch):
    client = env["client"]
    token = env["token_a"]

    # Clock moved to 2026-11-10T18:31:00Z (00:01 IST on Nov 11).
    # Today in IST is Nov 11. Grace period 1 day -> 00:00 IST of Nov 10 = 2026-11-09T18:30:00Z.
    clock_next_day_ist = datetime(2026, 11, 10, 18, 31, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(bookings_service, "_now_utc", lambda: clock_next_day_ist)

    # 1. 2026-11-09T18:29:59Z rejected (just outside new boundary)
    start_outside = datetime(2026, 11, 9, 18, 29, 59, tzinfo=timezone.utc)
    res_outside = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start_outside.isoformat(),
            "endDate": (start_outside + timedelta(days=2)).isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res_outside.status_code == 422
    assert "grace window" in res_outside.text

    # 2. 2026-11-09T18:30:00Z accepted (just inside new boundary)
    start_inside = datetime(2026, 11, 9, 18, 30, 0, tzinfo=timezone.utc)
    res_inside = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start_inside.isoformat(),
            "endDate": (start_inside + timedelta(days=2)).isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res_inside.status_code == 201


def test_grace_window_zero_days_means_start_of_today_ist(env, monkeypatch):
    client = env["client"]
    token = env["token_a"]

    # booking_grace_period_days = 0 means start of today in IST (00:00 IST on Nov 10).
    # Converted to UTC: 2026-11-09T18:30:00Z.
    monkeypatch.setattr(settings, "booking_grace_period_days", 0)
    monkeypatch.setattr(bookings_service, "_now_utc", lambda: FROZEN_CLOCK)

    # 1. 2026-11-09T18:29:59Z rejected (just outside)
    start_outside = datetime(2026, 11, 9, 18, 29, 59, tzinfo=timezone.utc)
    res_outside = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start_outside.isoformat(),
            "endDate": (start_outside + timedelta(days=2)).isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res_outside.status_code == 422
    assert "grace window" in res_outside.text

    # 2. 2026-11-09T18:30:00Z accepted (just inside)
    start_inside = datetime(2026, 11, 9, 18, 30, 0, tzinfo=timezone.utc)
    res_inside = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": start_inside.isoformat(),
            "endDate": (start_inside + timedelta(days=2)).isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res_inside.status_code == 201


def test_unauthenticated_post_bookings_returns_401(env):
    client = env["client"]
    res = client.post(
        "/api/v1/bookings",
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Airport Terminal 1",
        },
    )
    assert res.status_code == 401


def test_unauthenticated_get_availability_returns_401(env):
    client = env["client"]
    res = client.get(
        "/api/v1/bookings/availability",
        params={
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
        },
    )
    assert res.status_code == 401


def test_cross_tenant_availability_returns_404_no_leak(env):
    client = env["client"]
    token_a = env["token_a"]

    res = client.get(
        "/api/v1/bookings/availability",
        headers={"Authorization": f"Bearer {token_a}"},
        params={
            "vehicleId": env["vehicle_b_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
        },
    )
    assert res.status_code == 404
    assert res.json()["error"]["message"] == "Vehicle not found."


def test_cross_tenant_customer_returns_404(env):
    client = env["client"]
    token_a = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "customerId": env["customer_b_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Airport Terminal 1",
        },
    )
    assert res.status_code == 404
    assert "Customer not found." in res.text


def test_soft_deleted_vehicle_returns_404(env, mock_db):
    client = env["client"]
    token_a = env["token_a"]

    # Mark vehicle as soft-deleted
    mock_db.vehicles.update_one(
        {"_id": env["vehicle_a_oid"]},
        {"$set": {"deletedAt": datetime.now(timezone.utc)}},
    )

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 404
    assert "Vehicle not found." in res.text


def test_soft_deleted_customer_returns_404(env, mock_db):
    client = env["client"]
    token_a = env["token_a"]

    # Mark customer as soft-deleted
    mock_db.customers.update_one(
        {"_id": env["customer_a_oid"]},
        {"$set": {"deletedAt": datetime.now(timezone.utc)}},
    )

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 404
    assert "Customer not found." in res.text


# ===========================================================================
# 2. Integer Ceil-Division Billable Days Math
# ===========================================================================
def test_billable_days_exact_24_hours():
    start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert calculate_billable_days(start, start + timedelta(hours=24)) == 1


def test_billable_days_24_hours_and_one_minute():
    start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert calculate_billable_days(start, start + timedelta(hours=24, minutes=1)) == 2


def test_billable_days_25_hours():
    start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert calculate_billable_days(start, start + timedelta(hours=25)) == 2


def test_billable_days_exact_48_hours():
    start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert calculate_billable_days(start, start + timedelta(hours=48)) == 2


def test_billable_days_48_hours_and_one_second():
    start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert calculate_billable_days(start, start + timedelta(hours=48, seconds=1)) == 3


# ===========================================================================
# 3. Rate Guard, Snapshot Immutability, & bookingGuard Behaviour
# ===========================================================================
def test_snapshot_rate_equals_vehicle_stored_rate(env):
    client = env["client"]
    token = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Main Branch",
        },
    )
    assert res.status_code == 201
    booking = res.json()["data"]

    expected_rate_paise = float_to_paise(2500)
    assert booking["dailyRatePaise"] == expected_rate_paise


def test_vehicle_with_zero_or_missing_rate_returns_409(env, mock_db):
    client = env["client"]
    token = env["token_a"]

    # Set vehicle dailyRate and price to 0
    mock_db.vehicles.update_one(
        {"_id": env["vehicle_a_oid"]},
        {"$set": {"dailyRate": 0, "price": 0}},
    )

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Main Branch",
        },
    )
    assert res.status_code == 409
    assert res.json()["error"]["message"] == "Vehicle has no valid daily rate."


def test_rate_snapshot_immutable_on_vehicle_update(env, mock_db):
    client = env["client"]
    token = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Main Branch",
            "discountPaise": 50000,
        },
    )
    assert res.status_code == 201
    booking_id = res.json()["data"]["id"]

    # Mutate vehicle rate in DB
    mock_db.vehicles.update_one(
        {"_id": env["vehicle_a_oid"]},
        {"$set": {"dailyRate": 5000, "price": 5000}},
    )

    stored_booking = mock_db.bookings.find_one({"_id": ObjectId(booking_id)})
    assert stored_booking["dailyRatePaise"] == 250000
    assert stored_booking["baseAmountPaise"] == 500000
    assert stored_booking["totalAmountPaise"] == 450000


def test_entity_snapshot_immutable_on_vehicle_update(env, mock_db):
    client = env["client"]
    token = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Main Branch",
        },
    )
    assert res.status_code == 201
    booking_id = res.json()["data"]["id"]

    # Mutate vehicle name and registration in DB
    mock_db.vehicles.update_one(
        {"_id": env["vehicle_a_oid"]},
        {"$set": {"name": "Changed Name", "registration": "NEW 99 ZZ 9999"}},
    )

    stored_booking = mock_db.bookings.find_one({"_id": ObjectId(booking_id)})
    assert stored_booking["vehicleSnapshot"]["name"] == "Hyundai Creta"
    assert stored_booking["vehicleSnapshot"]["registration"] == "KA 01 AB 1234"


def test_booking_guard_excluded_from_vehicle_api(env):
    client = env["client"]
    token = env["token_a"]

    veh_res = client.get(
        f"/api/v1/vehicles/{env['vehicle_a_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert veh_res.status_code == 200
    assert "bookingGuard" not in veh_res.json()["data"]


def test_booking_guard_does_not_modify_vehicle_updated_at(env, mock_db):
    client = env["client"]
    token = env["token_a"]

    vehicle_before = mock_db.vehicles.find_one({"_id": env["vehicle_a_oid"]})
    initial_updated_at = vehicle_before["updatedAt"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-01T10:00:00Z",
            "endDate": "2026-12-03T10:00:00Z",
            "pickupLocation": "Downtown Hub",
        },
    )
    assert res.status_code == 201

    vehicle_after = mock_db.vehicles.find_one({"_id": env["vehicle_a_oid"]})
    assert vehicle_after["bookingGuard"] == 1
    assert vehicle_after["updatedAt"] == initial_updated_at


def test_vehicle_patch_after_booking_preserves_booking_guard(env, mock_db):
    client = env["client"]
    token = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-01T10:00:00Z",
            "endDate": "2026-12-03T10:00:00Z",
            "pickupLocation": "Downtown Hub",
        },
    )
    assert res.status_code == 201
    assert mock_db.vehicles.find_one({"_id": env["vehicle_a_oid"]})["bookingGuard"] == 1

    patch_res = client.patch(
        f"/api/v1/vehicles/{env['vehicle_a_id']}",
        headers={"Authorization": f"Bearer {token}"},
        data={"color": "Metallic Blue"},
    )
    assert patch_res.status_code == 200

    vehicle_db = mock_db.vehicles.find_one({"_id": env["vehicle_a_oid"]})
    assert vehicle_db["color"] == "Metallic Blue"
    assert vehicle_db["bookingGuard"] == 1


# ===========================================================================
# 4. Overlap Conflict Matrix (8 Cases Against Pending, Confirmed, Active)
# ===========================================================================
BLOCKING_STATUSES = ["Pending", "Confirmed", "Active"]


@pytest.fixture
def base_booking_seeded(env):
    def _seed(status: str) -> str:
        res = env["client"].post(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={
                "customerId": env["customer_a_id"],
                "vehicleId": env["vehicle_a_id"],
                "startDate": "2026-12-10T10:00:00Z",
                "endDate": "2026-12-15T10:00:00Z",
                "pickupLocation": "HQ",
                "status": status,
            },
        )
        assert res.status_code == 201, res.text
        return res.json()["data"]["id"]
    return _seed


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case1_strictly_before(env, base_booking_seeded, blocking_status):
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-01T10:00:00Z",
            "endDate": "2026-12-05T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 201


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case2_strictly_after(env, base_booking_seeded, blocking_status):
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-20T10:00:00Z",
            "endDate": "2026-12-25T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 201


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case3_identical_interval(env, base_booking_seeded, blocking_status):
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-15T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 409


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case4_enclosing_interval(env, base_booking_seeded, blocking_status):
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-08T10:00:00Z",
            "endDate": "2026-12-17T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 409


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case5_enclosed_interval(env, base_booking_seeded, blocking_status):
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-11T10:00:00Z",
            "endDate": "2026-12-14T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 409


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case6_overlapping_start(env, base_booking_seeded, blocking_status):
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-08T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 409


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case7_overlapping_end(env, base_booking_seeded, blocking_status):
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-13T10:00:00Z",
            "endDate": "2026-12-18T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 409


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case8a_touching_start_no_conflict(env, base_booking_seeded, blocking_status):
    # Candidate ends exactly when base starts: [Dec 5 10:00, Dec 10 10:00) vs [Dec 10 10:00, Dec 15 10:00)
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-05T10:00:00Z",
            "endDate": "2026-12-10T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 201


@pytest.mark.parametrize("blocking_status", BLOCKING_STATUSES)
def test_overlap_case8b_touching_end_no_conflict(env, base_booking_seeded, blocking_status):
    # Candidate starts exactly when base ends: [Dec 15 10:00, Dec 20 10:00) vs [Dec 10 10:00, Dec 15 10:00)
    base_booking_seeded(blocking_status)
    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-15T10:00:00Z",
            "endDate": "2026-12-20T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 201


@pytest.mark.parametrize("non_blocking_status", ["Cancelled", "Completed", "No-show"])
def test_non_blocking_statuses_do_not_conflict(env, mock_db, non_blocking_status):
    mock_db.bookings.insert_one({
        "tenantId": env["tenant_a_id"],
        "bookingNumber": "BK-2026-OLD",
        "customerId": env["customer_a_oid"],
        "vehicleId": env["vehicle_a_oid"],
        "startDate": datetime(2026, 12, 10, 10, 0, 0, tzinfo=timezone.utc),
        "endDate": datetime(2026, 12, 15, 10, 0, 0, tzinfo=timezone.utc),
        "pickupLocation": "HQ",
        "status": non_blocking_status,
        "dailyRatePaise": 250000,
        "billableDays": 5,
        "baseAmountPaise": 1250000,
        "discountPaise": 0,
        "securityDepositPaise": 500000,
        "totalAmountPaise": 1250000,
        "vehicleSnapshot": {},
        "customerSnapshot": {},
        "createdAt": env["now"],
        "updatedAt": env["now"],
        "deletedAt": None,
    })

    res = env["client"].post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-15T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 201


def test_failed_overlap_leaves_zero_booking_documents_in_db(env, mock_db):
    client = env["client"]
    token = env["token_a"]

    # 1. Create base booking
    res1 = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-15T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res1.status_code == 201
    assert mock_db.bookings.count_documents({}) == 1

    # 2. Candidate attempts conflicting slot -> 409
    res2 = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-12T10:00:00Z",
            "endDate": "2026-12-14T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res2.status_code == 409

    # Assert exactly 1 booking exists (no phantom document left by failed candidate)
    assert mock_db.bookings.count_documents({}) == 1


# ===========================================================================
# 5. Discount Authorization Rules
# ===========================================================================
def test_staff_discount_greater_than_zero_rejected(env):
    client = env["client"]
    token_staff = env["token_staff_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_staff}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Branch",
            "discountPaise": 10000,
        },
    )
    assert res.status_code == 403
    assert "Staff members cannot apply discounts." in res.text


def test_staff_discount_zero_allowed(env):
    client = env["client"]
    token_staff = env["token_staff_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_staff}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Branch",
            "discountPaise": 0,
        },
    )
    assert res.status_code == 201


def test_manager_discount_within_base_amount_allowed(env):
    client = env["client"]
    token_manager = env["token_manager_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_manager}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Branch",
            "discountPaise": 150000,
        },
    )
    assert res.status_code == 201
    assert res.json()["data"]["discountPaise"] == 150000


def test_owner_discount_within_base_amount_allowed(env):
    client = env["client"]
    token_owner = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_owner}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Branch",
            "discountPaise": 200000,
        },
    )
    assert res.status_code == 201
    assert res.json()["data"]["discountPaise"] == 200000


def test_owner_discount_exceeding_base_amount_rejected(env):
    client = env["client"]
    token_owner = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_owner}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-10T10:00:00Z",
            "endDate": "2026-12-12T10:00:00Z",
            "pickupLocation": "Branch",
            "discountPaise": 600000,
        },
    )
    assert res.status_code == 422
    assert "exceed base rental amount" in res.text


# ===========================================================================
# 6. Availability Endpoint and Exclude Booking ID
# ===========================================================================
def test_availability_endpoint_slot_available(env):
    client = env["client"]
    token = env["token_a"]

    r = client.get(
        "/api/v1/bookings/availability",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-20T10:00:00Z",
            "endDate": "2026-12-25T10:00:00Z",
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["available"] is True
    assert len(r.json()["data"]["conflicts"]) == 0


def test_availability_endpoint_slot_unavailable(env):
    client = env["client"]
    token = env["token_a"]

    create_res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-20T10:00:00Z",
            "endDate": "2026-12-25T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert create_res.status_code == 201

    r = client.get(
        "/api/v1/bookings/availability",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-20T10:00:00Z",
            "endDate": "2026-12-25T10:00:00Z",
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["available"] is False
    assert len(r.json()["data"]["conflicts"]) == 1


def test_availability_endpoint_exclude_booking_id(env):
    client = env["client"]
    token = env["token_a"]

    create_res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-20T10:00:00Z",
            "endDate": "2026-12-25T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert create_res.status_code == 201
    booking_id = create_res.json()["data"]["id"]

    r = client.get(
        "/api/v1/bookings/availability",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-20T10:00:00Z",
            "endDate": "2026-12-25T10:00:00Z",
            "excludeBookingId": booking_id,
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["available"] is True


# ===========================================================================
# 7. Vehicle Under Maintenance Rejection (409)
# ===========================================================================
def test_vehicle_under_maintenance_returns_409(env, mock_db):
    client = env["client"]
    token = env["token_a"]

    mock_db.vehicles.update_one(
        {"_id": env["vehicle_a_oid"]},
        {"$set": {"availability": "Maintenance"}},
    )

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-28T10:00:00Z",
            "endDate": "2026-12-30T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 409
    assert "maintenance" in res.text.lower()


# ===========================================================================
# 8. Cross-Tenant Vehicle Booking Rejection (404)
# ===========================================================================
def test_cross_tenant_vehicle_booking_returns_404(env):
    client = env["client"]
    token_a = env["token_a"]

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_b_id"],
            "startDate": "2026-12-28T10:00:00Z",
            "endDate": "2026-12-30T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 404
    assert "Vehicle not found" in res.text


# ===========================================================================
# 9. Transaction Timeout (503) Envelope Test
# ===========================================================================
def test_transaction_timeout_returns_503_envelope(env, monkeypatch):
    client = env["client"]
    token_a = env["token_a"]

    def raise_timeout(*args, **kwargs):
        raise BookingTransactionTimeoutError("Database transaction timed out.")

    monkeypatch.setattr(bookings_service, "execute_in_transaction", raise_timeout)

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": "2026-12-28T10:00:00Z",
            "endDate": "2026-12-30T10:00:00Z",
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 503
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body["error"]["message"] == "Service temporarily unavailable. Please retry."


# ===========================================================================
# 10. Atomic Booking Number Generator Tests
# ===========================================================================
def test_booking_numbers_sequential_for_same_tenant_and_year(mock_db):
    t1 = ObjectId()
    bk1 = generate_booking_number(mock_db, t1, year=2026)
    bk2 = generate_booking_number(mock_db, t1, year=2026)
    assert bk1 == "BK-2026-0001"
    assert bk2 == "BK-2026-0002"


def test_booking_numbers_restart_for_different_tenant(mock_db):
    t1 = ObjectId()
    t2 = ObjectId()
    generate_booking_number(mock_db, t1, year=2026)
    bk_t2 = generate_booking_number(mock_db, t2, year=2026)
    assert bk_t2 == "BK-2026-0001"


def test_booking_numbers_restart_for_different_year(mock_db):
    t1 = ObjectId()
    generate_booking_number(mock_db, t1, year=2026)
    bk_2027 = generate_booking_number(mock_db, t1, year=2027)
    assert bk_2027 == "BK-2027-0001"
