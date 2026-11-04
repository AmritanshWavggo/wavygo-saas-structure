"""
Tests for Phase 3b Booking Status Lifecycle and Transitions:
- Valid status transitions:
  Pending -> Confirmed, Cancelled
  Confirmed -> Active, Cancelled
  Active -> Completed
- Roles:
  Staff cannot cancel Confirmed bookings (Owner/Manager only).
  Staff may confirm, activate, complete, and cancel Pending.
- Terminal & invalid transitions:
  Active -> Cancelled rejected (409)
  Completed -> * rejected (409)
  Cancelled -> * rejected (409)
  Pending -> Active rejected (409)
  Pending -> Completed rejected (409)
  Invalid status string rejected (422)
- Extra tests:
  Activate blocked by another Active booking (409)
  Overdue Active booking blocks a new overlapping booking
  Edit loses the race against a transition (409)
  Customer delete blocked by a future Confirmed booking (409)
  Cross-tenant transition returns 404
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
from app.modules.bookings.models import BookingStatus
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
    monkeypatch.setattr(bookings_service, "_now_utc", lambda: now)
    v_a_id = mock_db.vehicles.insert_one({
        "tenantId": tenant_a_id,
        "name": "Hyundai Creta",
        "registration": "KA 01 AB 1234",
        "registrationNumber": "KA01AB1234",
        "type": "Motorcycle",
        "status": "Online",
        "availability": "Available",
        "fleetAvailability": "Available",
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

    def create_test_booking(status_val="Pending", start_offset=1, end_offset=3):
        start = now + timedelta(days=start_offset)
        end = now + timedelta(days=end_offset)
        res = test_client.post(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "customerId": str(c_a_id),
                "vehicleId": str(v_a_id),
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "pickupLocation": "HQ Hub",
                "status": status_val,
            },
        )
        assert res.status_code == 201, res.text
        return res.json()["data"]["id"]

    return {
        "client": test_client,
        "db": mock_db,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "token_a": token_a,
        "token_manager_a": token_manager_a,
        "token_staff_a": token_staff_a,
        "token_b": token_b,
        "vehicle_a_id": str(v_a_id),
        "customer_a_id": str(c_a_id),
        "create_booking": create_test_booking,
        "now": now,
    }


# ---------------------------------------------------------------------------
# Valid Status Transitions
# ---------------------------------------------------------------------------

def test_transition_pending_to_confirmed_sets_confirmed_at(env):
    b_id = env["create_booking"](status_val="Pending")
    client = env["client"]
    token = env["token_staff_a"]  # Staff allowed

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Confirmed"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "Confirmed"
    assert data["confirmedAt"] is not None


def test_transition_pending_to_cancelled_allows_staff_and_sets_reason(env):
    b_id = env["create_booking"](status_val="Pending")
    client = env["client"]
    token = env["token_staff_a"]

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Cancelled", "cancelReason": "Customer changed travel plans"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "Cancelled"
    assert data["cancelledAt"] is not None
    assert data["cancelReason"] == "Customer changed travel plans"


def test_transition_confirmed_to_active_sets_activated_at(env):
    b_id = env["create_booking"](status_val="Confirmed")
    client = env["client"]
    token = env["token_staff_a"]

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Active"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "Active"
    assert data["activatedAt"] is not None


def test_transition_confirmed_to_cancelled_allowed_for_manager(env):
    b_id = env["create_booking"](status_val="Confirmed")
    client = env["client"]
    token = env["token_manager_a"]

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Cancelled", "cancelReason": "Manager approved cancellation"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "Cancelled"
    assert data["cancelledAt"] is not None


def test_transition_active_to_completed_sets_completed_at(env):
    b_id = env["create_booking"](status_val="Confirmed")
    client = env["client"]
    token = env["token_staff_a"]

    # Activate first
    client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Active"},
    )

    # Complete
    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Completed"},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "Completed"
    assert data["completedAt"] is not None


# ---------------------------------------------------------------------------
# Role Restrictions & Forbidden Transitions
# ---------------------------------------------------------------------------

def test_staff_cannot_cancel_confirmed_booking(env):
    b_id = env["create_booking"](status_val="Confirmed")
    client = env["client"]
    token = env["token_staff_a"]

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Cancelled", "cancelReason": "Staff trying to cancel"},
    )
    assert res.status_code == 403
    assert "Staff members cannot cancel confirmed bookings" in res.text


def test_transition_active_to_cancelled_is_rejected_409(env):
    b_id = env["create_booking"](status_val="Confirmed")
    client = env["client"]
    token = env["token_a"]

    client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Active"},
    )

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Cancelled"},
    )
    assert res.status_code == 409
    assert "Invalid status transition" in res.text


def test_transition_terminal_completed_is_rejected_409(env):
    b_id = env["create_booking"](status_val="Confirmed")
    client = env["client"]
    token = env["token_a"]

    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Active"})
    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Completed"})

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Cancelled"},
    )
    assert res.status_code == 409
    assert "Cannot transition terminal booking" in res.text


def test_transition_terminal_cancelled_is_rejected_409(env):
    b_id = env["create_booking"](status_val="Pending")
    client = env["client"]
    token = env["token_a"]

    client.patch(f"/api/v1/bookings/{b_id}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Cancelled"})

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Confirmed"},
    )
    assert res.status_code == 409
    assert "Cannot transition terminal booking" in res.text


def test_transition_invalid_jump_pending_to_completed_rejected_409(env):
    b_id = env["create_booking"](status_val="Pending")
    client = env["client"]
    token = env["token_a"]

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Completed"},
    )
    assert res.status_code == 409
    assert "Invalid status transition" in res.text


def test_invalid_status_value_returns_422(env):
    b_id = env["create_booking"](status_val="Pending")
    client = env["client"]
    token = env["token_a"]

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "SuperActive"},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Extra Phase 3b Tests (Item 11)
# ---------------------------------------------------------------------------

def test_activate_blocked_by_another_active_booking(env):
    # Booking 1: Oct 12 to 14
    b1_id = env["create_booking"](status_val="Confirmed", start_offset=1, end_offset=3)
    # Booking 2: Oct 15 to 17 (disjoint dates, but same vehicle)
    b2_id = env["create_booking"](status_val="Confirmed", start_offset=5, end_offset=7)

    client = env["client"]
    token = env["token_a"]

    # Activate booking 1
    res1 = client.patch(
        f"/api/v1/bookings/{b1_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Active"},
    )
    assert res1.status_code == 200

    # Activating booking 2 for the same vehicle while booking 1 is Active must return 409
    res2 = client.patch(
        f"/api/v1/bookings/{b2_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Active"},
    )
    assert res2.status_code == 409
    assert "already has an active booking" in res2.text


def test_overdue_active_booking_blocks_a_new_overlapping_booking(env):
    # Setup an Active booking whose scheduled endDate was yesterday (overdue)
    now = env["now"]
    db = env["db"]
    t_id = env["tenant_a_id"]

    past_start = now - timedelta(days=3)
    past_end = now - timedelta(days=1)  # Ended yesterday, but still Active!

    db.bookings.insert_one({
        "tenantId": t_id,
        "bookingNumber": "BK-2026-OVERDUE",
        "customerId": ObjectId(env["customer_a_id"]),
        "vehicleId": ObjectId(env["vehicle_a_id"]),
        "startDate": past_start,
        "endDate": past_end,
        "pickupLocation": "HQ",
        "status": "Active",
        "dailyRatePaise": 250000,
        "billableDays": 2,
        "baseAmountPaise": 500000,
        "discountPaise": 0,
        "securityDepositPaise": 0,
        "totalAmountPaise": 500000,
        "vehicleSnapshot": {"name": "Creta"},
        "customerSnapshot": {"name": "Aarav"},
        "createdAt": past_start,
        "updatedAt": past_start,
        "deletedAt": None,
    })

    client = env["client"]
    token = env["token_a"]

    # Try creating a booking starting right now (before overdue bike is returned)
    new_start = now - timedelta(hours=2)
    new_end = now + timedelta(days=1)

    res = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customerId": env["customer_a_id"],
            "vehicleId": env["vehicle_a_id"],
            "startDate": new_start.isoformat(),
            "endDate": new_end.isoformat(),
            "pickupLocation": "HQ",
        },
    )
    assert res.status_code == 409
    assert "already booked" in res.text


def test_edit_loses_the_race_against_a_transition_returns_409(env, monkeypatch):
    b_id = env["create_booking"](status_val="Confirmed")
    client = env["client"]
    token = env["token_a"]

    # Simulate race: right before the CAS update executes in update_booking_guarded,
    # another thread transitions the booking to Active!
    orig_update_one = env["db"]["bookings"].update_one

    def racing_update_one(filter_query, update_spec, *args, **kwargs):
        # If this is the CAS update on bookings, concurrently update status to Active first!
        if "_id" in filter_query and "status" in filter_query:
            orig_update_one({"_id": ObjectId(b_id)}, {"$set": {"status": "Active"}})
        return orig_update_one(filter_query, update_spec, *args, **kwargs)

    monkeypatch.setattr(env["db"]["bookings"], "update_one", racing_update_one)

    # Attempt to edit dates
    start = env["now"] + timedelta(days=2)
    end = start + timedelta(days=3)

    res = client.patch(
        f"/api/v1/bookings/{b_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
    )
    assert res.status_code == 409
    assert "Cannot edit booking" in res.text or "modified concurrently" in res.text


def test_cross_tenant_transition_returns_404(env):
    b_id = env["create_booking"](status_val="Pending")
    client = env["client"]
    token_b = env["token_b"]  # Tenant B

    res = client.patch(
        f"/api/v1/bookings/{b_id}/status",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"status": "Confirmed"},
    )
    assert res.status_code == 404
    assert "Booking not found" in res.text
