from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.payments.service import payment_service
from app.modules.bookings.service import booking_service
from app.modules.dashboard.service import dashboard_service

client = TestClient(app)


def test_get_dashboard_stats():
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    data = response.json()

    assert "total_vehicles" in data
    assert "available_vehicles" in data
    assert "rented_vehicles" in data
    assert "active_bookings" in data
    assert "total_revenue" in data
    assert "fleet_utilization" in data
    assert "revenue_trend" in data
    assert "recent_bookings" in data
    assert "rented_vehicles_list" in data

    assert isinstance(data["revenue_trend"], list)
    assert isinstance(data["recent_bookings"], list)
    assert isinstance(data["rented_vehicles_list"], list)


def test_get_dashboard_alias():
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "total_vehicles" in data
    assert "upcoming_arrivals" in data
    assert isinstance(data["upcoming_arrivals"], list)


def test_get_upcoming_arrivals():
    response = client.get("/api/v1/dashboard/arrivals")
    assert response.status_code == 200
    arrivals = response.json()
    assert isinstance(arrivals, list)
    assert len(arrivals) > 0
    assert "bookingId" in arrivals[0]
    assert "expectedAt" in arrivals[0]


def test_mark_arrival_as_arrived():
    response = client.patch("/api/v1/dashboard/arrivals/BK-3985/arrive")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "Arrived"
    assert res["booking_id"] == "BK-3985"

    # Verify status reflects in arrivals list
    list_res = client.get("/api/v1/dashboard/arrivals")
    assert list_res.status_code == 200
    item = next((a for a in list_res.json() if a["bookingId"] == "BK-3985"), None)
    assert item is not None
    assert item["status"] == "Arrived"


def test_dashboard_revenue_excludes_cancelled_and_pending_payments(monkeypatch):
    monkeypatch.setattr(dashboard_service, "_get_db", lambda: None)
    payment_service._memory_payments["TX-TEST-PAID"] = {
        "id": "TX-TEST-PAID",
        "booking": "BK-TEST-PAID",
        "customer": "Test Paid",
        "method": "UPI",
        "date": "Nov 19, 2026",
        "amount": 1250.75,
        "status": "Paid",
        "created_at": "2026-11-19T00:00:00+00:00",
        "updated_at": "2026-11-19T00:00:00+00:00",
    }
    payment_service._memory_payments["TX-TEST-PARTIAL"] = {
        "id": "TX-TEST-PARTIAL",
        "booking": "BK-TEST-PARTIAL",
        "customer": "Test Partial",
        "method": "Cash",
        "date": "Nov 18, 2026",
        "amount": 249.25,
        "status": "Partial",
        "created_at": "2026-11-18T09:00:00+00:00",
        "updated_at": "2026-11-18T09:00:00+00:00",
    }
    payment_service._memory_payments["TX-TEST-PENDING"] = {
        "id": "TX-TEST-PENDING",
        "booking": "BK-TEST-PENDING",
        "customer": "Test Pending",
        "method": "Cash",
        "date": "Nov 19, 2026",
        "amount": 500.0,
        "status": "Pending",
        "created_at": "2026-11-19T09:00:00+00:00",
        "updated_at": "2026-11-19T09:00:00+00:00",
    }
    payment_service._memory_payments["TX-TEST-CANCELLED"] = {
        "id": "TX-TEST-CANCELLED",
        "booking": "BK-TEST-CANCELLED",
        "customer": "Test Cancelled",
        "method": "Cash",
        "date": "Nov 19, 2026",
        "amount": 900.0,
        "status": "Paid",
        "created_at": "2026-11-19T09:00:00+00:00",
        "updated_at": "2026-11-19T09:00:00+00:00",
    }
    booking_service._memory_bookings["BK-TEST-CANCELLED"] = {
        "id": "BK-TEST-CANCELLED",
        "customer": "Test Cancelled",
        "vehicle": "Test Scooter",
        "dates": "Nov 19 – Nov 20",
        "status": "Cancelled",
        "paid": 900.0,
        "pending": 0.0,
        "base_amount": 900.0,
        "add_on_amount": 0.0,
        "service_fee": 0.0,
        "discount_amount": 0.0,
        "deposit_amount": 0.0,
        "total_amount": 900.0,
        "rental_days": 1,
        "vehicle_details": {},
        "customer_details": {},
        "rental_details": {},
        "payment_details": {},
        "created_at": "2026-11-19T09:00:00+00:00",
        "updated_at": "2026-11-19T09:00:00+00:00",
    }

    response = client.get("/api/v1/dashboard/stats?range=Last%2030%20days")
    assert response.status_code == 200
    assert response.json()["total_revenue"] == 1500.0

    for payment_id in [
        "TX-TEST-PAID",
        "TX-TEST-PARTIAL",
        "TX-TEST-PENDING",
        "TX-TEST-CANCELLED",
    ]:
        payment_service._memory_payments.pop(payment_id, None)
    booking_service._memory_bookings.pop("BK-TEST-CANCELLED", None)


