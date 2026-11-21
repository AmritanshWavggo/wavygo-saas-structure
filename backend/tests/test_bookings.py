from fastapi.testclient import TestClient
from app.main import app
from app.modules.bookings.service import booking_service

client = TestClient(app)


def test_create_offline_booking():
    payload = {
        "vehicle": {
            "vehicle_id": "VH-1042",
            "vehicle_name": "Honda Activa 6G",
            "registration": "GJ 05 AB 4821",
            "price_per_day": 649,
            "vehicle_type": "Scooter",
        },
        "customer": {
            "name": "Ravi Kumar",
            "phone": "+91 98989 12345",
            "email": "ravi.kumar@example.com",
            "aadhaar": "123456789012",
            "driving_licence": "GJ0520211234567",
        },
        "rental": {
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "pickup_time": "10:00",
            "return_time": "18:00",
            "pickup_location": "Vesu Hub, Surat",
            "add_ons": True,
            "discount": 100,
        },
        "payment": {
            "method": "Cash",
            "deposit": True,
            "paid_amount": 0,
        },
        "notes": "Customer presented valid driving license.",
    }

    response = client.post("/api/v1/bookings/offline", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["type"] == "Offline"
    assert data["status"] == "Confirmed"
    assert data["customer"] == "Ravi Kumar"
    assert data["vehicle"] == "Honda Activa 6G"
    assert data["rental_days"] == 2
    # Base: 649 * 2 = 1298
    assert data["base_amount"] == 1298.0
    # Add-on: 500 * 2 = 1000
    assert data["add_on_amount"] == 1000.0
    # Service fee: 5% of 1298 = 64.9
    assert data["service_fee"] == 64.9
    # Subtotal: 1298 + 1000 + 64.9 = 2362.9
    # Discount: 100
    # Deposit: 2000
    # Total: 2362.9 - 100 + 2000 = 4262.9
    assert round(data["total_amount"], 1) == 4262.9
    assert data["paid"] == 0.0
    assert round(data["pending"], 1) == 4262.9


def test_list_and_get_offline_bookings():
    # List bookings
    list_res = client.get("/api/v1/bookings/offline")
    assert list_res.status_code == 200
    bookings = list_res.json()
    assert len(bookings) >= 1

    booking_id = bookings[0]["id"]
    # Get by ID
    get_res = client.get(f"/api/v1/bookings/offline/{booking_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == booking_id

    # Test search query
    query_res = client.get(f"/api/v1/bookings/offline?query=Ravi")
    assert query_res.status_code == 200
    assert len(query_res.json()) >= 1


def test_update_status_and_payment(monkeypatch):
    from datetime import datetime, timezone
    import uuid

    from bson import ObjectId
    from app.modules.auth.security import get_current_vendor
    import mongomock

    mock_db = mongomock.MongoClient()["wavygo_test"]
    mock_db["payments"].create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string", "$gt": ""}},
    )
    mock_db["payments"].create_index(
        [("tenant_id", 1), ("booking", 1), ("transaction_reference", 1)],
        unique=True,
        partialFilterExpression={"transaction_reference": {"$type": "string", "$gt": ""}},
    )
    monkeypatch.setattr("app.modules.payments.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.bookings.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.notifications.service.get_database", lambda: mock_db)

    tenant_id = str(ObjectId())
    booking_id = f"BK-TEST-{uuid.uuid4().hex[:8]}"
    total_amount = 1899.0
    now = datetime.now(timezone.utc).isoformat()
    mock_db["bookings"].insert_one({
        "id": booking_id,
        "customer": "Pooja Verma",
        "vehicle": "Royal Enfield Classic 350",
        "dates": "Nov 05 – Nov 06",
        "type": "Offline",
        "status": "Active",
        "paid": 0.0,
        "pending": total_amount,
        "base_amount": total_amount,
        "add_on_amount": 0.0,
        "service_fee": 0.0,
        "discount_amount": 0.0,
        "deposit_amount": 0.0,
        "total_amount": total_amount,
        "rental_days": 1,
        "vehicle_details": {
            "id": "VH-1038",
            "name": "Royal Enfield Classic 350",
            "registration": "GJ 05 CD 7194",
            "price_per_day": 1899.0,
        },
        "customer_details": {"id": "CU-1", "name": "Pooja Verma", "phone": "+91 91234 56789"},
        "rental_details": {"start_date": "2026-11-05", "end_date": "2026-11-06", "pickup_location": "Adajan Center"},
        "payment_details": {"transactions": []},
        "tenant_id": tenant_id,
        "vendor_id": tenant_id,
        "created_at": now,
        "updated_at": now,
    })

    def authenticated_vendor():
        return {"_id": ObjectId(tenant_id), "email": "booking-test@example.com", "is_active": True}

    app.dependency_overrides[get_current_vendor] = authenticated_vendor

    try:
        # Record partial payment
        pay_res = client.post(
            f"/api/v1/bookings/offline/{booking_id}/payments",
            json={
                "amount": 500,
                "method": "UPI",
                "notes": "UPI reference 123456789",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert pay_res.status_code == 200
        pay_data = pay_res.json()
        assert pay_data["paid"] == 500.0
        assert pay_data["pending"] == round(total_amount - 500.0, 2)

        # Update status to Completed
        patch_res = client.patch(
            f"/api/v1/bookings/offline/{booking_id}",
            json={"status": "Completed"},
        )
        assert patch_res.status_code == 409
    finally:
        app.dependency_overrides.pop(get_current_vendor, None)


def test_booking_not_found():
    res = client.get("/api/v1/bookings/offline/BK-999999")
    assert res.status_code == 404


def _offline_booking_payload(customer_overrides=None):
    customer = {
        "name": "Test Customer",
        "phone": "+91 98765 43210",
        "aadhaar": "123456789012",
        "driving_licence": "GJ0520211234567",
    }
    if customer_overrides:
        customer.update(customer_overrides)
    return {
        "vehicle": {
            "vehicle_id": "VH-TEST",
            "vehicle_name": "Test Scooter",
            "registration": "GJ 05 TEST 123",
            "price_per_day": 500,
        },
        "customer": customer,
        "rental": {
            "start_date": "2026-11-20",
            "end_date": "2026-11-21",
            "pickup_location": "Test Desk",
        },
        "payment": {
            "method": "Cash",
        },
    }


def test_offline_booking_rejects_missing_or_invalid_aadhaar():
    missing_aadhaar = _offline_booking_payload()
    missing_aadhaar["customer"].pop("aadhaar")
    assert client.post("/api/v1/bookings/offline", json=missing_aadhaar).status_code == 422

    for aadhaar in (None, "", "12345678901", "1234567890123", "12345678901a"):
        invalid_aadhaar = _offline_booking_payload({"aadhaar": aadhaar})
        assert client.post("/api/v1/bookings/offline", json=invalid_aadhaar).status_code == 422


def test_offline_booking_accepts_valid_aadhaar_with_optional_dl():
    dl_cases = (
        (False, None),
        (True, None),
        (True, ""),
        (True, "GJ0520211234567"),
    )
    for dl_is_provided, dl_value in dl_cases:
        customer_overrides = {"driving_licence": dl_value} if dl_is_provided else {}
        payload = _offline_booking_payload(customer_overrides)
        if not dl_is_provided:
            payload["customer"].pop("driving_licence")

        response = client.post("/api/v1/bookings/offline", json=payload)
        assert response.status_code == 201
        booking = booking_service._memory_bookings[response.json()["id"]]
        assert booking["aadhaar_number"] == "123456789012"
        assert booking["driving_licence_number"] == (
            "GJ0520211234567" if dl_value == "GJ0520211234567" else None
        )


def test_offline_booking_bill_uses_consistent_two_decimal_rounding(monkeypatch):
    from bson import ObjectId
    from app.modules.auth.security import get_current_vendor
    import mongomock

    mock_db = mongomock.MongoClient()["booking_rounding_test"]
    mock_db["payments"].create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string", "$gt": ""}},
    )
    mock_db["payments"].create_index(
        [("tenant_id", 1), ("booking", 1), ("transaction_reference", 1)],
        unique=True,
        partialFilterExpression={"transaction_reference": {"$type": "string", "$gt": ""}},
    )
    tenant_id = str(ObjectId())
    monkeypatch.setattr("app.modules.bookings.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.payments.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.notifications.service.get_database", lambda: mock_db)
    monkeypatch.setattr("app.modules.bookings.router._get_tenant_id", lambda request: tenant_id)

    def authenticated_vendor():
        return {"_id": ObjectId(tenant_id), "email": "rounding-test@example.com", "is_active": True}

    app.dependency_overrides[get_current_vendor] = authenticated_vendor
    payload = _offline_booking_payload()
    payload["vehicle"]["price_per_day"] = 649.99
    payload["rental"]["start_date"] = "2026-11-20"
    payload["rental"]["end_date"] = "2026-11-21"
    payload["rental"]["add_ons"] = False
    payload["rental"]["discount"] = 10.005
    payload["payment"]["paid_amount"] = 50.555
    payload["payment"]["deposit"] = False

    try:
        response = client.post("/api/v1/bookings/offline", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["base_amount"] == 649.99
        assert data["service_fee"] == 32.5
        assert data["discount_amount"] == 10.01
        assert data["total_amount"] == 672.48
        # The booking service rounds the requested 50.555 advance to ₹50.56,
        # then records that rounded amount through the payment service.
        assert data["paid"] == 50.56
        assert data["pending"] == 621.92
        assert mock_db["payments"].find_one({"booking": data["id"], "amount": 50.56}) is not None
    finally:
        app.dependency_overrides.pop(get_current_vendor, None)
