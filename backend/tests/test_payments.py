from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
import mongomock
from pydantic import SecretStr
from pymongo.errors import PyMongoError
import pytest

from app.core.config import settings
from app.main import app
from app.modules.auth.security import get_current_vendor
from app.modules.customers.router import get_customers_collection
from app.modules.payments.schemas import PaymentCreate
from app.modules.payments.service import payment_service


def make_test_booking(booking_id: str, tenant_id: str, total: float = 5000.0, paid: float = 0.0, status: str = "Active", **kwargs) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": booking_id,
        "customer": kwargs.get("customer", "Test Customer"),
        "vehicle": kwargs.get("vehicle", "Honda Activa 6G"),
        "dates": "Oct 10 – Oct 15",
        "type": "Offline",
        "status": status,
        "paid": float(paid),
        "pending": max(0.0, float(total - paid)),
        "base_amount": float(total),
        "add_on_amount": 0.0,
        "service_fee": 0.0,
        "discount_amount": 0.0,
        "deposit_amount": 0.0,
        "total_amount": float(total),
        "rental_days": 5,
        "vehicle_details": {"id": "VH-1", "name": "Honda Activa 6G", "price_per_day": 1000.0},
        "customer_details": {"id": kwargs.get("customer_id", "CU-1"), "name": kwargs.get("customer", "Test Customer"), "phone": kwargs.get("phone", "+91 99999 88888")},
        "rental_details": {"start_date": "2026-10-10", "end_date": "2026-10-15", "pickup_location": "Main Store"},
        "payment_details": {"transactions": []},
        "tenant_id": str(tenant_id),
        "vendor_id": str(tenant_id),
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    doc.update(kwargs)
    return doc


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    db = client["wavygo_test"]
    # Create indexes
    db["payments"].create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string", "$gt": ""}},
    )
    db["payments"].create_index(
        [("tenant_id", 1), ("booking", 1), ("transaction_reference", 1)],
        unique=True,
        partialFilterExpression={"transaction_reference": {"$type": "string", "$gt": ""}},
    )
    return db


@pytest.fixture
def payment_service_db(mock_db, monkeypatch):
    """Service-level Mongo mock for concurrency tests; does not start TestClient."""
    monkeypatch.setattr("app.modules.payments.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.notifications.service.get_database", lambda: mock_db)
    return mock_db, str(ObjectId())


@pytest.fixture
def auth_client(mock_db, monkeypatch):
    tenant_a_id = str(ObjectId())
    tenant_b_id = str(ObjectId())

    monkeypatch.setattr("app.modules.payments.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.bookings.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.notifications.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.main.create_mongo_client", lambda: None)
    monkeypatch.setattr("app.main.ensure_vehicle_indexes", lambda: None)
    monkeypatch.setattr("app.main.ensure_payment_indexes", lambda: None)

    app.dependency_overrides[get_customers_collection] = lambda: mock_db["customers"]

    token_a = f"test-token-a-{tenant_a_id}"
    token_b = f"test-token-b-{tenant_b_id}"

    def mock_get_current_vendor(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Could not validate credentials.")
        token = auth_header.split(" ", 1)[1].strip()
        if token == token_a:
            return {"_id": ObjectId(tenant_a_id), "email": "vendor_a@test.com", "is_active": True}
        elif token == token_b:
            return {"_id": ObjectId(tenant_b_id), "email": "vendor_b@test.com", "is_active": True}
        raise HTTPException(status_code=401, detail="Could not validate credentials.")

    app.dependency_overrides[get_current_vendor] = mock_get_current_vendor
    app.state.database = mock_db

    with TestClient(app) as test_client:
        yield {
            "client": test_client,
            "db": mock_db,
            "tenant_a_id": tenant_a_id,
            "tenant_b_id": tenant_b_id,
            "headers_a": {"Authorization": f"Bearer {token_a}"},
            "headers_b": {"Authorization": f"Bearer {token_b}"},
        }

    app.dependency_overrides.clear()
    app.state.database = None


def test_unauthenticated_recording_rejected(auth_client):
    client = auth_client["client"]
    res = client.post("/api/v1/payments", json={
        "booking_id": "BK-123",
        "amount": 500.0,
        "method": "Cash",
        "idempotency_key": str(uuid.uuid4()),
    })
    assert res.status_code == 401


def test_partial_and_full_payment_flow(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    # Seed booking
    b_id = "BK-1001"
    db["bookings"].insert_one(make_test_booking(b_id, t_id, total=5000.0, paid=1000.0, customer="Aarav Mehta"))

    # 1. Record Partial Payment: ₹2,000 via Cash
    res1 = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b_id,
            "amount": 2000.0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
            "notes": "Counter cash deposit",
        },
        headers=headers,
    )
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["amount"] == 2000.0
    assert data1["status"] == "Partial"

    # Verify booking status and outstanding
    b_doc = db["bookings"].find_one({"id": b_id})
    assert b_doc["paid"] == 3000.0
    assert b_doc["pending"] == 2000.0

    b_res = client.get(f"/api/v1/bookings/offline/{b_id}", headers=headers)
    assert b_res.status_code == 200
    b_json = b_res.json()
    assert b_json["paid"] == 3000.0
    assert b_json["outstanding"] == 2000.0
    assert b_json["payment_status"] == "Partially Paid"

    # 2. Record Full Final Payment: ₹2,000 via UPI
    res2 = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b_id,
            "amount": 2000.0,
            "method": "UPI",
            "transaction_reference": "UPI/9876543210",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res2.status_code == 201
    assert res2.json()["status"] == "Paid"

    b_res2 = client.get(f"/api/v1/bookings/offline/{b_id}", headers=headers)
    assert b_res2.status_code == 200
    b_json2 = b_res2.json()
    assert b_json2["paid"] == 5000.0
    assert b_json2["outstanding"] == 0.0
    assert b_json2["payment_status"] == "Paid"


def test_reject_overpayment(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    b_id = "BK-1002"
    db["bookings"].insert_one(make_test_booking(b_id, t_id, total=3000.0, paid=2500.0, customer="Isha Patel"))

    # Attempt to pay ₹600 when only ₹500 is outstanding
    res = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b_id,
            "amount": 600.0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res.status_code == 409
    assert "exceeds outstanding balance" in res.json()["detail"].lower()


def test_reject_zero_and_negative_amount(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers_a"]

    res_zero = client.post(
        "/api/v1/payments",
        json={
            "booking_id": "BK-1003",
            "amount": 0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res_zero.status_code == 422

    res_neg = client.post(
        "/api/v1/payments",
        json={
            "booking_id": "BK-1003",
            "amount": -100.0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res_neg.status_code == 422


def test_idempotency_replay_and_conflict(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    b_id = "BK-1004"
    db["bookings"].insert_one(make_test_booking(b_id, t_id, total=4000.0, paid=1000.0, customer="Rohan Shah"))

    key = str(uuid.uuid4())
    payload = {
        "booking_id": b_id,
        "amount": 1000.0,
        "method": "Cash",
        "idempotency_key": key,
        "notes": "First attempt",
    }

    # Initial request
    res1 = client.post("/api/v1/payments", json=payload, headers=headers)
    assert res1.status_code == 201
    tx_id = res1.json()["id"]

    # Replay identical payload with same idempotency key
    res2 = client.post("/api/v1/payments", json=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["id"] == tx_id

    # Verify booking paid wasn't incremented twice
    b_doc = db["bookings"].find_one({"id": b_id})
    assert b_doc["paid"] == 2000.0

    # Same idempotency key with different payload -> 409
    conflict_payload = {
        "booking_id": b_id,
        "amount": 500.0,
        "method": "Cash",
        "idempotency_key": key,
    }
    res3 = client.post("/api/v1/payments", json=conflict_payload, headers=headers)
    assert res3.status_code == 409
    assert "idempotency key already used" in res3.json()["detail"].lower()


def test_duplicate_transaction_reference_constraints(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    b1 = "BK-1005"
    b2 = "BK-1006"
    for b in (b1, b2):
        db["bookings"].insert_one(make_test_booking(b, t_id, total=5000.0, paid=0.0))

    ref = "UPI/DUPLICATE-REF-100"

    # Payment on B1 with ref
    res1 = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b1,
            "amount": 1000.0,
            "method": "UPI",
            "transaction_reference": ref,
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res1.status_code == 201

    # Same reference on SAME booking -> 409
    res2 = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b1,
            "amount": 500.0,
            "method": "UPI",
            "transaction_reference": ref,
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res2.status_code == 409
    assert "already been recorded for this booking" in res2.json()["detail"].lower()

    # Same reference on DIFFERENT booking (B2) -> Allowed (201)
    res3 = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b2,
            "amount": 500.0,
            "method": "UPI",
            "transaction_reference": ref,
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res3.status_code == 201


def test_non_cash_without_reference_rejected(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers_a"]

    # Non-cash without reference
    res = client.post(
        "/api/v1/payments",
        json={
            "booking_id": "BK-1007",
            "amount": 500.0,
            "method": "Card",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert "transaction reference is required" in str(res.json()).lower()


def test_future_date_rejected(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers_a"]

    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    res = client.post(
        "/api/v1/payments",
        json={
            "booking_id": "BK-1008",
            "amount": 500.0,
            "method": "Cash",
            "payment_date": future_date,
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert "future" in str(res.json()).lower()


def test_cancelled_booking_rejected(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    b_id = "BK-1009"
    db["bookings"].insert_one(make_test_booking(b_id, t_id, total=2000.0, paid=0.0, status="Cancelled"))

    res = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b_id,
            "amount": 500.0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res.status_code == 409
    assert "cancelled booking" in res.json()["detail"].lower()


def test_cross_tenant_isolation(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers_b = auth_client["headers_b"]
    t_a = auth_client["tenant_a_id"]

    b_id = "BK-1010"
    db["bookings"].insert_one(make_test_booking(b_id, t_a, total=2000.0, paid=0.0, customer="Customer A"))

    # Tenant B attempts to record payment on Tenant A's booking
    res = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b_id,
            "amount": 500.0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers_b,
    )
    assert res.status_code == 404


def test_customer_dues_single_aggregation(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    cust_id = ObjectId()
    db["customers"].insert_one({
        "_id": cust_id,
        "tenant_id": ObjectId(t_id),
        "name": "Neha Sharma",
        "phone": "+91 91234 56789",
        "phone_normalized": "919123456789",
        "email": "neha@test.com",
        "status": "Verified",
        "bookings": 2,
        "active": 1,
        "paid": 0,  # Old counter
        "pending": 0,  # Old counter
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    # Booking 1: Active, Total ₹3,000, Paid ₹1,000 -> Pending ₹2,000
    db["bookings"].insert_one(make_test_booking(
        "BK-2001",
        t_id,
        total=3000.0,
        paid=1000.0,
        customer="Neha Sharma",
        customer_id=str(cust_id),
        phone="+91 91234 56789",
        deletedAt=None,
    ))

    # Booking 2: Cancelled, Total ₹4,000, Paid ₹500, Pending ₹3,500 -> Excluded from dues!
    db["bookings"].insert_one(make_test_booking(
        "BK-2002",
        t_id,
        total=4000.0,
        paid=500.0,
        status="Cancelled",
        customer="Neha Sharma",
        customer_id=str(cust_id),
        phone="+91 91234 56789",
        deletedAt=None,
    ))

    # Call GET /api/v1/customers/
    res = client.get("/api/v1/customers/", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 1
    cust_item = next(item for item in items if item["id"] == str(cust_id))

    # Should only aggregate the non-cancelled booking (Paid=1000, Pending=2000)
    assert cust_item["paid"] == 1000.0
    assert cust_item["pending"] == 2000.0


def test_booking_router_record_payment_delegation(auth_client):
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    b_id = "BK-3001"
    db["bookings"].insert_one(make_test_booking(b_id, t_id, total=4000.0, paid=1000.0, customer="Vikram Seth"))

    # Call /api/v1/bookings/offline/{booking_id}/payments
    res = client.post(
        f"/api/v1/bookings/offline/{b_id}/payments",
        json={
            "amount": 1500.0,
            "method": "UPI",
            "transaction_reference": "UPI/SETTLED-3001",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["paid"] == 2500.0
    assert data["outstanding"] == 1500.0
    assert data["payment_status"] == "Partially Paid"

    # Verify payment record was created in payments collection
    p_doc = db["payments"].find_one({"booking": b_id})
    assert p_doc is not None
    assert p_doc["amount"] == 1500.0
    assert p_doc["method"] == "UPI"


def test_read_endpoints_and_stats(auth_client):
    client = auth_client["client"]
    headers = auth_client["headers_a"]

    # List payments
    res = client.get("/api/v1/payments", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Stats
    stats_res = client.get("/api/v1/payments/stats", headers=headers)
    assert stats_res.status_code == 200
    s_data = stats_res.json()
    assert "total_collected" in s_data
    assert "pending_balance" in s_data


def test_concurrent_atomic_update_prevents_overpayment(auth_client):
    """
    Test conditional atomic update with $expr:
    When two concurrent payments of ₹2,500 are attempted against an outstanding balance of ₹3,000,
    the conditional atomic update ensures the second payment fails with 409 Conflict.
    """
    client = auth_client["client"]
    db = auth_client["db"]
    headers = auth_client["headers_a"]
    t_id = auth_client["tenant_a_id"]

    b_id = "BK-CONCURRENT-1"
    db["bookings"].insert_one(make_test_booking(b_id, t_id, total=5000.0, paid=2000.0))

    # Payment 1 succeeds
    res1 = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b_id,
            "amount": 2500.0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res1.status_code == 201

    # Payment 2 attempts to record ₹2,500 concurrently, but outstanding is now only ₹500
    res2 = client.post(
        "/api/v1/payments",
        json={
            "booking_id": b_id,
            "amount": 2500.0,
            "method": "Cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert res2.status_code == 409
    assert "exceeds outstanding balance" in res2.json()["detail"].lower()

    # Final booking paid is exactly ₹4,500 (never exceeds ₹5,000)
    b_doc = db["bookings"].find_one({"id": b_id})
    assert b_doc["paid"] == 4500.0
    assert b_doc["pending"] == 500.0


def test_concurrent_different_payments_use_current_booking_values(payment_service_db):
    """Two different concurrent payments are both represented exactly once."""
    db, tenant_id = payment_service_db
    booking_id = "BK-CONCURRENT-DIFFERENT"
    db["bookings"].insert_one(make_test_booking(booking_id, tenant_id, total=1000.0))

    payloads = [
        PaymentCreate(booking_id=booking_id, amount=250.0, method="Cash", idempotency_key=str(uuid.uuid4())),
        PaymentCreate(booking_id=booking_id, amount=350.0, method="Cash", idempotency_key=str(uuid.uuid4())),
    ]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda payload: payment_service.record_payment_with_replay(payload, tenant_id), payloads))

    assert all(not is_replay for _, is_replay in results)
    booking = db["bookings"].find_one({"id": booking_id})
    payments = list(db["payments"].find({"booking": booking_id}))
    transaction_total = sum(tx["amount"] for tx in booking["payment_details"]["transactions"])
    payment_total = sum(payment["amount"] for payment in payments)
    assert len(payments) == 2
    assert booking["paid"] == payment_total == transaction_total == 600.0
    assert booking["paid"] <= booking["total_amount"]


def test_concurrent_same_idempotency_key_records_one_payment(payment_service_db):
    """A raced idempotency collision compensates its booking increment and replays."""
    db, tenant_id = payment_service_db
    booking_id = "BK-CONCURRENT-IDEMPOTENT"
    db["bookings"].insert_one(make_test_booking(booking_id, tenant_id, total=1000.0))
    payload = PaymentCreate(
        booking_id=booking_id,
        amount=250.0,
        method="Cash",
        idempotency_key=str(uuid.uuid4()),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: payment_service.record_payment_with_replay(payload, tenant_id), range(2)))

    booking = db["bookings"].find_one({"id": booking_id})
    payments = list(db["payments"].find({"booking": booking_id}))
    assert len(payments) == 1
    assert booking["paid"] == 250.0
    assert booking["pending"] == 750.0
    assert {is_replay for _, is_replay in results} <= {False, True}
    assert any(not is_replay for _, is_replay in results)


def test_insert_failure_compensates_only_its_own_booking_increment(payment_service_db, monkeypatch):
    """Rollback preserves a payment that lands between the failed update and compensation."""
    db, tenant_id = payment_service_db
    booking_id = "BK-COMPENSATION"
    db["bookings"].insert_one(make_test_booking(booking_id, tenant_id, total=1000.0))

    outer = PaymentCreate(booking_id=booking_id, amount=200.0, method="Cash", idempotency_key="outer-fail")
    inner = PaymentCreate(booking_id=booking_id, amount=300.0, method="Cash", idempotency_key="inner-success")
    collection_type = type(db["payments"])
    original_insert_one = collection_type.insert_one
    injected = False

    def fail_outer_insert(self, document, *args, **kwargs):
        nonlocal injected
        if self.name == "payments" and document.get("idempotency_key") == outer.idempotency_key and not injected:
            injected = True
            payment_service.record_payment_with_replay(inner, tenant_id)
            raise PyMongoError("forced payment insert failure")
        return original_insert_one(self, document, *args, **kwargs)

    monkeypatch.setattr(collection_type, "insert_one", fail_outer_insert)
    with pytest.raises(HTTPException) as exc_info:
        payment_service.record_payment_with_replay(outer, tenant_id)

    assert exc_info.value.status_code == 503
    booking = db["bookings"].find_one({"id": booking_id})
    payments = list(db["payments"].find({"booking": booking_id}))
    transactions = booking["payment_details"]["transactions"]
    assert booking["paid"] == 300.0
    assert booking["pending"] == 700.0
    assert [payment["amount"] for payment in payments] == [300.0]
    assert [transaction["amount"] for transaction in transactions] == [300.0]
