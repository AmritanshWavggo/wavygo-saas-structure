"""
Tests for Phase 3b Bookings CRUD (List, Get, Edit, Delete):
- List with pagination, filters, search, sort whitelist + _id tiebreak, cross-tenant isolation, soft-deleted exclusion.
- Get with 200 envelope, 404 on not found, cross-tenant, and soft-deleted.
- Edit with pre-active restrictions, price recalculation from snapshot rate, self-exclusion in overlap, old/new total amounts.
- Delete soft-delete restrictions: only Pending and Cancelled by Owner/Manager, 409 on Confirmed/Active/Completed, 403 on staff.
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

    v_a_1_id = mock_db.vehicles.insert_one({
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

    v_a_2_id = mock_db.vehicles.insert_one({
        "tenantId": tenant_a_id,
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

    v_b_id = mock_db.vehicles.insert_one({
        "tenantId": tenant_b_id,
        "name": "KTM Duke",
        "registration": "MH 02 EF 9999",
        "registrationNumber": "MH02EF9999",
        "type": "Motorcycle",
        "status": "Online",
        "availability": "Available",
        "fleetAvailability": "Available",
        "dailyRate": 3000,
        "price": 3000,
        "securityDeposit": 6000,
        "bookingGuard": 0,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    c_a_1_id = mock_db.customers.insert_one({
        "tenantId": tenant_a_id,
        "name": "Aarav Sharma",
        "phone": "+919876543210",
        "email": "aarav@example.com",
        "status": "Verified",
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    c_a_2_id = mock_db.customers.insert_one({
        "tenantId": tenant_a_id,
        "name": "Neha Patel",
        "phone": "+919123456789",
        "email": "neha@example.com",
        "status": "Verified",
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    c_b_id = mock_db.customers.insert_one({
        "tenantId": tenant_b_id,
        "name": "Rohit Verma",
        "phone": "+919988776655",
        "email": "rohit@example.com",
        "status": "Verified",
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    def create_booking(client_token=token_a, vehicle_id=str(v_a_1_id), customer_id=str(c_a_1_id), status="Pending", days_ahead=1, duration_days=2, discount=0):
        start = now + timedelta(days=days_ahead)
        end = start + timedelta(days=duration_days)
        res = test_client.post(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {client_token}"},
            json={
                "customerId": customer_id,
                "vehicleId": vehicle_id,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "pickupLocation": "HQ Station",
                "status": status,
                "discountPaise": discount,
                "notes": f"Booking for {customer_id}",
            },
        )
        assert res.status_code == 201, res.text
        return res.json()["data"]

    return {
        "client": test_client,
        "db": mock_db,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "token_a": token_a,
        "token_manager_a": token_manager_a,
        "token_staff_a": token_staff_a,
        "token_b": token_b,
        "vehicle_a_1_id": str(v_a_1_id),
        "vehicle_a_2_id": str(v_a_2_id),
        "vehicle_b_id": str(v_b_id),
        "customer_a_1_id": str(c_a_1_id),
        "customer_a_2_id": str(c_a_2_id),
        "customer_b_id": str(c_b_id),
        "create_booking": create_booking,
        "now": now,
    }


def test_list_bookings_pagination_and_meta(env):
    client = env["client"]
    token = env["token_a"]

    # Create 3 bookings at non-overlapping slots
    env["create_booking"](days_ahead=1, duration_days=2)
    env["create_booking"](days_ahead=4, duration_days=2)
    env["create_booking"](days_ahead=7, duration_days=2)

    # Page 1, limit 2
    res = client.get("/api/v1/bookings?page=1&limit=2", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()["data"]
    meta = res.json()["meta"]

    assert len(data) == 2
    assert meta["page"] == 1
    assert meta["limit"] == 2
    assert meta["total"] == 3

    # Page 2, limit 2
    res2 = client.get("/api/v1/bookings?page=2&limit=2", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert len(data2) == 1


def test_list_bookings_limit_capped_at_100(env):
    client = env["client"]
    token = env["token_a"]

    res = client.get("/api/v1/bookings?limit=101", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422


def test_list_bookings_filter_by_status(env):
    client = env["client"]
    token = env["token_a"]

    b1 = env["create_booking"](days_ahead=1, duration_days=2, status="Pending")
    b2 = env["create_booking"](days_ahead=4, duration_days=2, status="Confirmed")

    res = client.get("/api/v1/bookings?status=Confirmed", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == b2["id"]
    assert items[0]["status"] == "Confirmed"


def test_list_bookings_filter_by_vehicle_and_customer(env):
    client = env["client"]
    token = env["token_a"]

    b1 = env["create_booking"](vehicle_id=env["vehicle_a_1_id"], customer_id=env["customer_a_1_id"], days_ahead=1)
    b2 = env["create_booking"](vehicle_id=env["vehicle_a_2_id"], customer_id=env["customer_a_2_id"], days_ahead=1)

    res = client.get(f"/api/v1/bookings?vehicleId={env['vehicle_a_2_id']}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == b2["id"]

    res_cust = client.get(f"/api/v1/bookings?customerId={env['customer_a_1_id']}", headers={"Authorization": f"Bearer {token}"})
    assert res_cust.status_code == 200
    cust_items = res_cust.json()["data"]
    assert len(cust_items) == 1
    assert cust_items[0]["id"] == b1["id"]


def test_list_bookings_search(env):
    client = env["client"]
    token = env["token_a"]

    b = env["create_booking"](days_ahead=1, duration_days=2)
    bk_num = b["bookingNumber"]

    # Search by bookingNumber
    res = client.get(f"/api/v1/bookings?search={bk_num}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1

    # Search by customer name
    res2 = client.get("/api/v1/bookings?search=Aarav", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    assert len(res2.json()["data"]) == 1

    # Search non-matching
    res3 = client.get("/api/v1/bookings?search=NonExistentXyz", headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 200
    assert len(res3.json()["data"]) == 0


def test_list_bookings_sort_whitelist_and_invalid_sort(env):
    client = env["client"]
    token = env["token_a"]

    env["create_booking"](days_ahead=5, duration_days=1)
    env["create_booking"](days_ahead=1, duration_days=2)

    # Valid sort asc by startDate
    res = client.get("/api/v1/bookings?sortBy=startDate&sortOrder=asc", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()["data"]
    assert items[0]["startDate"] < items[1]["startDate"]

    # Invalid sort field returns 422
    res_bad = client.get("/api/v1/bookings?sortBy=maliciousField", headers={"Authorization": f"Bearer {token}"})
    assert res_bad.status_code == 422
    assert "Invalid sortBy field" in res_bad.text


def test_list_bookings_tenant_isolation_and_excludes_soft_deleted(env):
    client = env["client"]
    token_a = env["token_a"]
    token_b = env["token_b"]

    b_a = env["create_booking"](client_token=token_a, days_ahead=1)
    b_b = env["create_booking"](
        client_token=token_b,
        vehicle_id=env["vehicle_b_id"],
        customer_id=env["customer_b_id"],
        days_ahead=1,
    )

    # Tenant A list sees only Tenant A
    res_a = client.get("/api/v1/bookings", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    ids_a = [x["id"] for x in res_a.json()["data"]]
    assert b_a["id"] in ids_a
    assert b_b["id"] not in ids_a

    # Soft-delete b_a
    del_res = client.delete(f"/api/v1/bookings/{b_a['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert del_res.status_code == 200

    # Soft-deleted booking excluded from list
    res_a_after = client.get("/api/v1/bookings", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_after.status_code == 200
    ids_after = [x["id"] for x in res_a_after.json()["data"]]
    assert b_a["id"] not in ids_after


def test_get_booking_by_id(env):
    client = env["client"]
    token_a = env["token_a"]
    token_b = env["token_b"]

    b = env["create_booking"](client_token=token_a, days_ahead=1)

    # Valid get
    res = client.get(f"/api/v1/bookings/{b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    assert res.json()["data"]["id"] == b["id"]
    assert res.json()["data"]["vehicleSnapshot"]["name"] == "Hyundai Creta"

    # Cross-tenant get returns 404
    res_b = client.get(f"/api/v1/bookings/{b['id']}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 404

    # Non-existent ID returns 404
    fake_id = str(ObjectId())
    res_fake = client.get(f"/api/v1/bookings/{fake_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_fake.status_code == 404

    # Soft-deleted returns 404
    client.delete(f"/api/v1/bookings/{b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    res_del = client.get(f"/api/v1/bookings/{b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_del.status_code == 404


def test_edit_booking_dates_and_recalculates_price_from_snapshot(env):
    client = env["client"]
    token = env["token_a"]
    db = env["db"]

    # Daily rate 2500 INR (250000 paise). 2 days = 500000 paise.
    b = env["create_booking"](days_ahead=1, duration_days=2, status="Pending")
    assert b["totalAmountPaise"] == 500000

    # Mutate vehicle's current dailyRate to 9999 INR in DB!
    # The recalculation MUST use snapshot rate (250000 paise), NOT the mutated vehicle rate.
    db.vehicles.update_one({"_id": ObjectId(env["vehicle_a_1_id"])}, {"$set": {"dailyRate": 9999, "price": 9999}})

    # Extend booking to 3 days (startDate remains, endDate + 1 day)
    now = env["now"]
    new_start = now + timedelta(days=1)
    new_end = now + timedelta(days=4)  # 3 days now

    edit_res = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "startDate": new_start.isoformat(),
            "endDate": new_end.isoformat(),
            "notes": "Updated notes",
        },
    )
    assert edit_res.status_code == 200, edit_res.text
    edited = edit_res.json()["data"]

    assert edited["billableDays"] == 3
    # 3 days * 250000 paise = 750000 paise
    assert edited["totalAmountPaise"] == 750000
    assert edited["oldTotalAmountPaise"] == 500000
    assert edited["newTotalAmountPaise"] == 750000
    assert edited["notes"] == "Updated notes"


def test_edit_booking_self_exclusion_in_overlap_check(env):
    client = env["client"]
    token = env["token_a"]
    now = env["now"]

    b = env["create_booking"](days_ahead=1, duration_days=3, status="Confirmed")

    # Shift end date earlier by 1 day (falls strictly inside original booking's own range)
    new_end = now + timedelta(days=3)
    res = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"endDate": new_end.isoformat()},
    )
    assert res.status_code == 200
    assert res.json()["data"]["billableDays"] == 2


def test_edit_booking_overlap_with_another_booking_returns_409(env):
    client = env["client"]
    token = env["token_a"]
    now = env["now"]

    b1 = env["create_booking"](days_ahead=1, duration_days=2)  # days 1..3
    b2 = env["create_booking"](days_ahead=4, duration_days=2)  # days 4..6

    # Attempt to edit b2 so its start date expands backwards to overlap b1
    res = client.patch(
        f"/api/v1/bookings/{b2['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"startDate": (now + timedelta(days=2)).isoformat()},
    )
    assert res.status_code == 409
    assert "already booked" in res.text


def test_edit_booking_vehicle_and_customer_change_before_active(env):
    client = env["client"]
    token = env["token_a"]

    b = env["create_booking"](
        vehicle_id=env["vehicle_a_1_id"],
        customer_id=env["customer_a_1_id"],
        days_ahead=1,
        duration_days=2,
    )
    assert b["totalAmountPaise"] == 500000

    # Switch to vehicle_a_2 (Hunter, rate 1500) and customer_a_2 (Neha)
    res = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "vehicleId": env["vehicle_a_2_id"],
            "customerId": env["customer_a_2_id"],
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["vehicleId"] == env["vehicle_a_2_id"]
    assert data["customerId"] == env["customer_a_2_id"]
    assert data["vehicleSnapshot"]["name"] == "Royal Enfield Hunter"
    assert data["customerSnapshot"]["name"] == "Neha Patel"
    # 2 days * 150000 = 300000 paise
    assert data["totalAmountPaise"] == 300000
    assert data["oldTotalAmountPaise"] == 500000
    assert data["newTotalAmountPaise"] == 300000


def test_edit_booking_cross_tenant_vehicle_or_customer_returns_404(env):
    client = env["client"]
    token = env["token_a"]

    b = env["create_booking"](days_ahead=1, duration_days=2)

    # Attempt to assign tenant B's vehicle
    res_veh = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"vehicleId": env["vehicle_b_id"]},
    )
    assert res_veh.status_code == 404
    assert "Vehicle not found" in res_veh.text

    # Attempt to assign tenant B's customer
    res_cust = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"customerId": env["customer_b_id"]},
    )
    assert res_cust.status_code == 404
    assert "Customer not found" in res_cust.text


def test_edit_booking_forbidden_after_active(env):
    client = env["client"]
    token = env["token_a"]
    now = env["now"]

    b = env["create_booking"](days_ahead=1, duration_days=2, status="Confirmed")

    # Transition to Active
    act_res = client.patch(
        f"/api/v1/bookings/{b['id']}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "Active"},
    )
    assert act_res.status_code == 200

    # Modifying dates on Active booking returns 409
    res_dates = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"endDate": (now + timedelta(days=5)).isoformat()},
    )
    assert res_dates.status_code == 409
    assert "Active bookings cannot modify" in res_dates.text

    # Modifying notes only on Active booking is allowed
    res_notes = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"notes": "Driver reported delay"},
    )
    assert res_notes.status_code == 200
    assert res_notes.json()["data"]["notes"] == "Driver reported delay"


def test_edit_booking_staff_cannot_apply_discount_returns_403(env):
    client = env["client"]
    token_staff = env["token_staff_a"]

    b = env["create_booking"](days_ahead=1, duration_days=2, status="Pending")

    res = client.patch(
        f"/api/v1/bookings/{b['id']}",
        headers={"Authorization": f"Bearer {token_staff}"},
        json={"discountPaise": 50000},
    )
    assert res.status_code == 403
    assert "Staff members cannot apply discounts" in res.text


def test_delete_booking_pending_or_cancelled_succeeds(env):
    client = env["client"]
    token_owner = env["token_a"]
    token_manager = env["token_manager_a"]

    # Owner deletes Pending
    b_pending = env["create_booking"](days_ahead=1, duration_days=2, status="Pending")
    del_p = client.delete(f"/api/v1/bookings/{b_pending['id']}", headers={"Authorization": f"Bearer {token_owner}"})
    assert del_p.status_code == 200
    assert del_p.json()["success"] is True

    # Manager deletes Cancelled
    b_cancelled = env["create_booking"](days_ahead=4, duration_days=2, status="Pending")
    # Cancel it first
    c_res = client.patch(
        f"/api/v1/bookings/{b_cancelled['id']}/status",
        headers={"Authorization": f"Bearer {token_manager}"},
        json={"status": "Cancelled", "cancelReason": "Customer changed mind"},
    )
    assert c_res.status_code == 200

    del_c = client.delete(f"/api/v1/bookings/{b_cancelled['id']}", headers={"Authorization": f"Bearer {token_manager}"})
    assert del_c.status_code == 200
    assert del_c.json()["success"] is True


def test_delete_booking_confirmed_active_or_completed_returns_409(env):
    client = env["client"]
    token = env["token_a"]

    # Confirmed booking cannot be deleted
    b_conf = env["create_booking"](days_ahead=1, duration_days=2, status="Confirmed")
    res_conf = client.delete(f"/api/v1/bookings/{b_conf['id']}", headers={"Authorization": f"Bearer {token}"})
    assert res_conf.status_code == 409
    assert "Cannot delete an active or confirmed booking" in res_conf.text

    # Active booking cannot be deleted
    client.patch(f"/api/v1/bookings/{b_conf['id']}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Active"})
    res_act = client.delete(f"/api/v1/bookings/{b_conf['id']}", headers={"Authorization": f"Bearer {token}"})
    assert res_act.status_code == 409

    # Completed booking cannot be deleted
    client.patch(f"/api/v1/bookings/{b_conf['id']}/status", headers={"Authorization": f"Bearer {token}"}, json={"status": "Completed"})
    res_comp = client.delete(f"/api/v1/bookings/{b_conf['id']}", headers={"Authorization": f"Bearer {token}"})
    assert res_comp.status_code == 409


def test_delete_booking_by_staff_returns_403(env):
    client = env["client"]
    token_staff = env["token_staff_a"]

    b = env["create_booking"](days_ahead=1, duration_days=2, status="Pending")
    res = client.delete(f"/api/v1/bookings/{b['id']}", headers={"Authorization": f"Bearer {token_staff}"})
    assert res.status_code == 403
    assert "Insufficient permissions to delete bookings" in res.text


def test_delete_booking_cross_tenant_returns_404(env):
    client = env["client"]
    token_a = env["token_a"]
    token_b = env["token_b"]

    b = env["create_booking"](client_token=token_a, days_ahead=1, duration_days=2, status="Pending")

    res = client.delete(f"/api/v1/bookings/{b['id']}", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404
