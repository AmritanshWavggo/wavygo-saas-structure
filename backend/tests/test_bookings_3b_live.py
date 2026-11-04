"""
Live tests for Bookings Phase 3b indexes (real MongoDB).
Gated by RUN_LIVE_CONCURRENCY_TESTS=true; DB name must contain "test".
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db import mongodb

pytestmark = pytest.mark.live_concurrency

NOW = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def live_client():
    if os.environ.get("RUN_LIVE_CONCURRENCY_TESTS", "").lower() != "true":
        pytest.skip("Set RUN_LIVE_CONCURRENCY_TESTS=true to run live tests")
    uri = os.environ.get("MONGODB_URI") or settings.mongodb_uri
    if not uri or "mongodb" not in uri:
        pytest.skip("MONGODB_URI is not set or invalid")
    name = os.environ.get("TEST_MONGODB_DATABASE", "wavygo_vendor_test_concurrency")
    if "test" not in name.lower():
        pytest.fail(f"Safety violation: database name '{name}' must contain 'test'")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    try:
        client.admin.command("hello")
    except Exception as exc:
        pytest.skip(f"Could not connect to MongoDB: {exc}")
    yield client, name
    client[name]["bookings"].drop()
    client.close()


@pytest.fixture()
def db(live_client, monkeypatch):
    client, name = live_client
    database = client[name]
    database["bookings"].drop()
    # Point the app's own ensure_indexes() at the test database.
    monkeypatch.setattr(mongodb, "get_database", lambda *a, **k: database)
    mongodb.ensure_indexes()
    names = set(database["bookings"].index_information().keys())
    assert "uq_bookings_tenant_vehicle_active" in names, f"index missing, got {names}"
    assert "uq_bookings_tenant_number" in names, f"index missing, got {names}"
    return database


def _booking(tenant, vehicle, status, number, deleted_at=None):
    return {
        "tenantId": tenant,
        "vehicleId": vehicle,
        "customerId": ObjectId(),
        "bookingNumber": number,
        "status": status,
        "startDate": NOW,
        "endDate": NOW,
        "createdAt": NOW,
        "updatedAt": NOW,
        "deletedAt": deleted_at,
    }


def test_second_active_booking_same_vehicle_rejected(db):
    t, v = ObjectId(), ObjectId()
    db["bookings"].insert_one(_booking(t, v, "Active", "B-1"))
    with pytest.raises(DuplicateKeyError):
        db["bookings"].insert_one(_booking(t, v, "Active", "B-2"))


def test_active_on_different_vehicles_allowed(db):
    t = ObjectId()
    db["bookings"].insert_one(_booking(t, ObjectId(), "Active", "B-1"))
    db["bookings"].insert_one(_booking(t, ObjectId(), "Active", "B-2"))


def test_active_same_vehicle_different_tenants_allowed(db):
    v = ObjectId()
    db["bookings"].insert_one(_booking(ObjectId(), v, "Active", "B-1"))
    db["bookings"].insert_one(_booking(ObjectId(), v, "Active", "B-1"))


def test_confirmed_bookings_do_not_hit_active_index(db):
    t, v = ObjectId(), ObjectId()
    db["bookings"].insert_one(_booking(t, v, "Confirmed", "B-1"))
    db["bookings"].insert_one(_booking(t, v, "Confirmed", "B-2"))
    db["bookings"].insert_one(_booking(t, v, "Active", "B-3"))


def test_cancelled_and_completed_do_not_block_new_active(db):
    t, v = ObjectId(), ObjectId()
    db["bookings"].insert_one(_booking(t, v, "Cancelled", "B-1"))
    db["bookings"].insert_one(_booking(t, v, "Completed", "B-2"))
    db["bookings"].insert_one(_booking(t, v, "Active", "B-3"))


def test_soft_deleted_active_does_not_block_new_active(db):
    t, v = ObjectId(), ObjectId()
    db["bookings"].insert_one(_booking(t, v, "Active", "B-1", deleted_at=NOW))
    db["bookings"].insert_one(_booking(t, v, "Active", "B-2"))


def test_duplicate_booking_number_same_tenant_rejected(db):
    t = ObjectId()
    db["bookings"].insert_one(_booking(t, ObjectId(), "Confirmed", "B-1"))
    with pytest.raises(DuplicateKeyError):
        db["bookings"].insert_one(_booking(t, ObjectId(), "Confirmed", "B-1"))


def test_same_booking_number_different_tenant_allowed(db):
    db["bookings"].insert_one(_booking(ObjectId(), ObjectId(), "Confirmed", "B-1"))
    db["bookings"].insert_one(_booking(ObjectId(), ObjectId(), "Confirmed", "B-1"))
    
    # ---------------------------------------------------------------------------
# Race tests (real MongoDB transactions)
# ---------------------------------------------------------------------------
import threading
from datetime import timedelta

from app.modules.bookings import service as svc
from app.modules.bookings.models import BookingStatus

ROLE = "owner"  # change if your owner role string differs
ROUNDS = 5


def _seed_vehicle_customer(db, tenant):
    v = db["vehicles"].insert_one({
        "tenantId": tenant, "name": "Tata Harrier", "registration": "MH 12 AB 9999",
        "registrationNumber": "MH12AB9999", "type": "Car", "status": "Online",
        "availability": "Available", "dailyRate": 3000, "price": 3000,
        "securityDeposit": 5000, "bookingGuard": 0,
        "createdAt": NOW, "updatedAt": NOW, "deletedAt": None,
    }).inserted_id
    c = db["customers"].insert_one({
        "tenantId": tenant, "name": "Live Test Customer", "phone": "+919999888877",
        "email": "livetest@example.com", "status": "Verified",
        "createdAt": NOW, "updatedAt": NOW, "deletedAt": None,
    }).inserted_id
    return v, c


def _confirmed_booking(client, db, tenant, vehicle, customer):
    now = datetime.now(timezone.utc)
    svc.create_booking_guarded(
        client=client, db=db, tenant_id=tenant, user_id=ObjectId(),
        vehicle_oid=vehicle, customer_oid=customer,
        start_date=now, end_date=now + timedelta(days=2),
        pickup_location="Test Pickup", status=BookingStatus("Confirmed"),
        clock_now=now,
    )
    return db["bookings"].find_one({"tenantId": tenant, "vehicleId": vehicle}, sort=[("createdAt", -1)])


def _clone_booking(db, doc, number):
    clone = dict(doc)
    clone.pop("_id")
    clone["bookingNumber"] = number
    return db["bookings"].insert_one(clone).inserted_id


def _race(fn_a, fn_b):
    barrier = threading.Barrier(2)
    out = {}

    def run(key, fn):
        barrier.wait()
        try:
            out[key] = ("ok", fn())
        except Exception as exc:  # noqa: BLE001
            out[key] = ("err", exc)

    threads = [threading.Thread(target=run, args=("a", fn_a)), threading.Thread(target=run, args=("b", fn_b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return out["a"], out["b"]


def _assert_domain_loser(res):
    assert res[0] == "err", "expected a failure"
    assert isinstance(res[1], svc.BookingDomainError), f"loser got {type(res[1]).__name__}: {res[1]}"


def test_cancel_vs_activate_exactly_one_wins(live_client, db):
    client, _ = live_client
    for _ in range(ROUNDS):
        db["bookings"].drop(); db["vehicles"].drop(); db["customers"].drop()
        mongodb.ensure_indexes()
        t = ObjectId()
        v, c = _seed_vehicle_customer(db, t)
        b = _confirmed_booking(client, db, t, v, c)
        a, x = _race(
            lambda: svc.transition_booking_status(db, t, b["_id"], BookingStatus("Active"), ROLE),
            lambda: svc.transition_booking_status(db, t, b["_id"], BookingStatus("Cancelled"), ROLE, cancel_reason="race"),
        )
        results = [a, x]
        assert sum(r[0] == "ok" for r in results) == 1, results
        loser = next(r for r in results if r[0] == "err")
        _assert_domain_loser(loser)
        winner_status = "Active" if a[0] == "ok" else "Cancelled"
        assert db["bookings"].find_one({"_id": b["_id"]})["status"] == winner_status


def test_two_activates_same_vehicle_exactly_one_wins(live_client, db):
    client, _ = live_client
    for _ in range(ROUNDS):
        db["bookings"].drop(); db["vehicles"].drop(); db["customers"].drop()
        mongodb.ensure_indexes()
        t = ObjectId()
        v, c = _seed_vehicle_customer(db, t)
        b1 = _confirmed_booking(client, db, t, v, c)
        b2_id = _clone_booking(db, b1, "B-RACE-2")
        a, x = _race(
            lambda: svc.transition_booking_status(db, t, b1["_id"], BookingStatus("Active"), ROLE),
            lambda: svc.transition_booking_status(db, t, b2_id, BookingStatus("Active"), ROLE),
        )
        assert sum(r[0] == "ok" for r in (a, x)) == 1, (a, x)
        _assert_domain_loser(next(r for r in (a, x) if r[0] == "err"))
        assert db["bookings"].count_documents({"tenantId": t, "vehicleId": v, "status": "Active"}) == 1


def test_edit_vs_cancel_no_corruption(live_client, db):
    client, _ = live_client
    for _ in range(ROUNDS):
        db["bookings"].drop(); db["vehicles"].drop(); db["customers"].drop()
        mongodb.ensure_indexes()
        t = ObjectId()
        v, c = _seed_vehicle_customer(db, t)
        b = _confirmed_booking(client, db, t, v, c)
        a, x = _race(
            lambda: svc.update_booking_guarded(client, db, t, b["_id"], ROLE, notes="edited"),
            lambda: svc.transition_booking_status(db, t, b["_id"], BookingStatus("Cancelled"), ROLE, cancel_reason="race"),
        )
        for r in (a, x):
            if r[0] == "err":
                assert isinstance(r[1], svc.BookingDomainError), f"{type(r[1]).__name__}: {r[1]}"
        assert x[0] == "ok", f"cancel should always win or follow the edit: {x}"
        assert db["bookings"].find_one({"_id": b["_id"]})["status"] == "Cancelled"