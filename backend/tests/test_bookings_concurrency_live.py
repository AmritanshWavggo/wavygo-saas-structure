"""
Live concurrency tests for Bookings module (Phase 3a).
Requires a live MongoDB replica set (Atlas or local).

Protected by:
1. Marker @pytest.mark.live_concurrency
2. Gated by RUN_LIVE_CONCURRENCY_TESTS="true"
3. Safety check: Database name MUST contain "test" (never touches production or dev data).

Verifies:
- Negative control (without guard via test monkeypatch): write-skew causes >1 bookings to be created for the same slot.
- Guarded run (with vehicle bookingGuard serialization point): exactly 1 booking succeeds (201), 9 fail with overlap conflict (409).
- Widened race window: guarded run also runs with the delayed overlap check.
- Aborted transaction rollback: vehicle bookingGuard in DB equals committed bookings.
- Non-overlapping concurrent runs: both bookings succeed (2x 201).
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pymongo import MongoClient

from app.core.config import settings
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.service import (
    OverlapConflictError,
    create_booking_guarded,
)

pytestmark = pytest.mark.live_concurrency


@pytest.fixture(scope="module")
def live_db():
    if os.environ.get("RUN_LIVE_CONCURRENCY_TESTS", "").lower() != "true":
        pytest.skip("Set RUN_LIVE_CONCURRENCY_TESTS=true to run live concurrency tests against MongoDB replica set")

    uri = os.environ.get("MONGODB_URI") or settings.mongodb_uri
    if not uri or "mongodb" not in uri:
        pytest.skip("MONGODB_URI is not set or invalid")

    test_db_name = os.environ.get("TEST_MONGODB_DATABASE", "wavygo_vendor_test_concurrency")
    # Section 8 Safety Check: Verify DB name explicitly contains 'test'
    if "test" not in test_db_name.lower():
        pytest.fail(f"Safety violation: Test database name '{test_db_name}' must contain 'test'")

    client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    try:
        hello_doc = client.admin.command("hello")
        if "setName" not in hello_doc:
            pytest.skip("Live MongoDB instance is not a replica set (missing setName)")
    except Exception as exc:
        pytest.skip(f"Could not connect to MongoDB replica set: {exc}")

    # Isolated test database
    db = client[test_db_name]

    # Setup: Clean up test collections prior to test run
    db["bookings"].drop()
    db["vehicles"].drop()
    db["customers"].drop()
    db["counters"].drop()

    # Create necessary indexes
    db["counters"].create_index([("tenantId", 1), ("sequence", 1)], unique=True)
    db["bookings"].create_index([("tenantId", 1), ("bookingNumber", 1)], unique=True)
    db["bookings"].create_index([("tenantId", 1), ("vehicleId", 1), ("status", 1), ("startDate", 1), ("endDate", 1)])

    try:
        yield {"client": client, "db": db}
    finally:
        # Teardown: Guaranteed cleanup after test module
        db["bookings"].drop()
        db["vehicles"].drop()
        db["customers"].drop()
        db["counters"].drop()
        client.close()


def _seed_tenant_entities(db):
    t_id = ObjectId()
    u_id = ObjectId()
    now = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

    v_id = db["vehicles"].insert_one({
        "tenantId": t_id,
        "name": "Tata Harrier",
        "registration": "MH 12 AB 9999",
        "registrationNumber": "MH12AB9999",
        "type": "Car",
        "status": "Online",
        "availability": "Available",
        "dailyRate": 3000,
        "price": 3000,
        "securityDeposit": 5000,
        "bookingGuard": 0,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    c_id = db["customers"].insert_one({
        "tenantId": t_id,
        "name": "Live Test Customer",
        "phone": "+919999888877",
        "email": "livetest@example.com",
        "status": "Verified",
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }).inserted_id

    return t_id, u_id, v_id, c_id


# ===========================================================================
# 1. Negative Control: Without Guard -> Write-Skew Demonstrates > 1 Winners
# ===========================================================================
def test_negative_control_without_guard_shows_write_skew(live_db, monkeypatch):
    """
    Test-only demonstration of write-skew:
    Monkeypatches apply_booking_guard to be a no-op (guard disabled) and delays overlap check,
    allowing concurrent transactions to commit overlapping bookings under MongoDB Snapshot Isolation.
    Retries up to 3 times to be tolerant of network latency jitter.
    """
    client = live_db["client"]
    db = live_db["db"]

    # Test-only guard bypass: no flags in production code
    monkeypatch.setattr(bookings_service, "apply_booking_guard", lambda *args, **kwargs: None)

    orig_overlap = bookings_service.check_overlap

    def delayed_overlap(*args, **kwargs):
        res = orig_overlap(*args, **kwargs)
        time.sleep(0.3)
        return res

    monkeypatch.setattr(bookings_service, "check_overlap", delayed_overlap)

    max_attempts = 3
    final_success_count = 0

    for attempt in range(1, max_attempts + 1):
        t_id, u_id, v_id, c_id = _seed_tenant_entities(db)
        start_date = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 12, 5, 10, 0, 0, tzinfo=timezone.utc)

        num_threads = 10
        barrier = threading.Barrier(num_threads)
        results: list[str] = []
        lock = threading.Lock()

        def worker(worker_id: int):
            barrier.wait()
            try:
                create_booking_guarded(
                    client=client,
                    db=db,
                    tenant_id=t_id,
                    user_id=u_id,
                    vehicle_oid=v_id,
                    customer_oid=c_id,
                    start_date=start_date,
                    end_date=end_date,
                    pickup_location="Hub 1",
                    status=BookingStatus.confirmed,
                )
                with lock:
                    results.append("201")
            except OverlapConflictError:
                with lock:
                    results.append("409")
            except Exception as exc:
                with lock:
                    results.append(f"ERR:{type(exc).__name__}: {exc}")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for f in futures:
                f.result()

        success_count = results.count("201")
        conflict_count = results.count("409")
        final_success_count = success_count

        print(f"\n[NEGATIVE CONTROL Attempt {attempt}] Results without guard: {success_count}x 201 Created, {conflict_count}x 409 Conflict")
        db_count = db["bookings"].count_documents({"tenantId": t_id, "vehicleId": v_id})
        print(f"[NEGATIVE CONTROL Attempt {attempt}] Actual documents inserted in DB: {db_count}")

        if success_count > 1:
            break

    assert final_success_count > 1, f"Expected write-skew to produce >1 winners, but got {final_success_count}"


# ===========================================================================
# 2. Guarded Run: With bookingGuard and Widened Race Window (Delayed Overlap)
# ===========================================================================
def test_guarded_concurrency_shows_exactly_one_winner(live_db, monkeypatch):
    """
    Standard production guarded run:
    apply_booking_guard serializes concurrent transactions on the vehicle document.
    Runs with the SAME delayed overlap check to prove serialization under widened race window.
    Asserts that:
    1. Exactly 1 transaction succeeds (201).
    2. Exactly 9 transactions receive 409 with the domain overlap-conflict message.
    3. The vehicle's bookingGuard in DB equals 1 (aborted transactions rolled back).
    """
    client = live_db["client"]
    db = live_db["db"]
    t_id, u_id, v_id, c_id = _seed_tenant_entities(db)

    # Apply the same delayed overlap check to widen the race window
    orig_overlap = bookings_service.check_overlap

    def delayed_overlap(*args, **kwargs):
        res = orig_overlap(*args, **kwargs)
        time.sleep(0.3)
        return res

    monkeypatch.setattr(bookings_service, "check_overlap", delayed_overlap)

    start_date = datetime(2026, 12, 10, 10, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2026, 12, 15, 10, 0, 0, tzinfo=timezone.utc)

    num_threads = 10
    barrier = threading.Barrier(num_threads)
    results: list[dict[str, str]] = []
    lock = threading.Lock()

    def worker(worker_id: int):
        barrier.wait()
        try:
            create_booking_guarded(
                client=client,
                db=db,
                tenant_id=t_id,
                user_id=u_id,
                vehicle_oid=v_id,
                customer_oid=c_id,
                start_date=start_date,
                end_date=end_date,
                pickup_location="Hub 1",
                status=BookingStatus.confirmed,
            )
            with lock:
                results.append({"status": "201", "message": "Created"})
        except OverlapConflictError as exc:
            with lock:
                results.append({"status": "409", "message": str(exc)})
        except Exception as exc:
            with lock:
                results.append({"status": "ERR", "message": f"{type(exc).__name__}: {exc}"})

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in futures:
            f.result()

    successes = [r for r in results if r["status"] == "201"]
    conflicts = [r for r in results if r["status"] == "409"]
    errors = [r for r in results if r["status"] not in ("201", "409")]

    print(f"\n[GUARDED RUN] Results with guard under widened window: {len(successes)}x 201 Created, {len(conflicts)}x 409 Conflict")
    db_count = db["bookings"].count_documents({"tenantId": t_id, "vehicleId": v_id})
    print(f"[GUARDED RUN] Actual documents inserted in DB: {db_count}")

    # No unhandled / transient errors
    assert len(errors) == 0, f"Unexpected errors: {errors}"

    # Exactly 1 transaction must succeed, exactly 9 must conflict
    assert len(successes) == 1, f"Expected exactly 1 winner, but got {len(successes)}"
    assert len(conflicts) == 9, f"Expected 9 conflicts, but got {len(conflicts)}"
    assert db_count == 1

    # Assert that EACH 409 is strictly the domain overlap conflict, NOT a mapped transient error
    for conflict in conflicts:
        assert conflict["message"] == "Vehicle is already booked for the selected rental period."

    # Assert bookingGuard on the vehicle equals the number of committed bookings (1)
    # Proves aborted transactions rolled back their $inc operations!
    vehicle_in_db = db["vehicles"].find_one({"_id": v_id})
    assert vehicle_in_db["bookingGuard"] == len(successes), (
        f"Vehicle bookingGuard ({vehicle_in_db['bookingGuard']}) must equal committed bookings ({len(successes)})"
    )


# ===========================================================================
# 3. Non-Overlapping Concurrent Test: Both 201 Created
# ===========================================================================
def test_non_overlapping_concurrent_bookings_both_succeed(live_db):
    client = live_db["client"]
    db = live_db["db"]
    t_id, u_id, v_id, c_id = _seed_tenant_entities(db)

    # Two distinct intervals for the same vehicle
    slot_1_start = datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc)
    slot_1_end = datetime(2026, 12, 5, 10, 0, 0, tzinfo=timezone.utc)

    slot_2_start = datetime(2026, 12, 5, 10, 0, 0, tzinfo=timezone.utc)
    slot_2_end = datetime(2026, 12, 10, 10, 0, 0, tzinfo=timezone.utc)

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def worker(start: datetime, end: datetime):
        barrier.wait()
        try:
            create_booking_guarded(
                client=client,
                db=db,
                tenant_id=t_id,
                user_id=u_id,
                vehicle_oid=v_id,
                customer_oid=c_id,
                start_date=start,
                end_date=end,
                pickup_location="Hub 1",
                status=BookingStatus.confirmed,
            )
            with lock:
                results.append("201")
        except OverlapConflictError:
            with lock:
                results.append("409")
        except Exception as exc:
            with lock:
                results.append(f"ERR:{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker, slot_1_start, slot_1_end)
        f2 = executor.submit(worker, slot_2_start, slot_2_end)
        f1.result()
        f2.result()

    success_count = results.count("201")
    conflict_count = results.count("409")

    print(f"\n[NON-OVERLAPPING] Results: {success_count}x 201 Created, {conflict_count}x 409 Conflict")
    db_count = db["bookings"].count_documents({"tenantId": t_id, "vehicleId": v_id})
    print(f"[NON-OVERLAPPING] Actual documents inserted in DB: {db_count}")

    # Both non-overlapping bookings must succeed
    assert success_count == 2, f"Expected both bookings to succeed, but got {success_count}"
    assert conflict_count == 0
    assert db_count == 2
