from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_reports_summary():
    response = client.get("/api/v1/reports/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_revenue" in data
    assert "active_bookings" in data
    assert "fleet_utilization" in data
    assert "total_customers" in data
    assert "total_vehicles" in data


def test_get_utilization_by_type():
    response = client.get("/api/v1/reports/utilization-by-type")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "type" in item
        assert "total" in item
        assert "rented" in item
        assert "utilization_pct" in item


def test_get_top_vehicles():
    response = client.get("/api/v1/reports/top-vehicles?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "id" in item
        assert "name" in item
        assert "bookings_count" in item


def test_get_trend():
    for sec in ["Overview", "Bookings", "Vehicles", "Maintenance", "Revenue"]:
        response = client.get(f"/api/v1/reports/trend?section={sec}&range=Last%206%20months")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6


def test_get_full_report():
    response = client.get("/api/v1/reports/full")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "utilization_by_type" in data
    assert "top_vehicles" in data
    assert "trend" in data


def test_export_csv():
    response = client.get("/api/v1/reports/export/csv")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/csv")
    assert "Booking ID" in response.text

