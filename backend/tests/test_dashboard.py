from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

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


