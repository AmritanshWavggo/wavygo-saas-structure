import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_maintenance():
    response = client.get("/api/v1/maintenance")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    # Default seeded record check (handles both DB seed and in-memory fallback)
    ids = [item["id"] for item in data]
    assert any(m_id in ids for m_id in ["MT-301", "MT-081"])


def test_list_maintenance_status_filter():
    response = client.get("/api/v1/maintenance?status=Ongoing")
    assert response.status_code == 200
    data = response.json()
    for item in data:
        assert item["status"] == "Ongoing"


def test_get_maintenance():
    response = client.get("/api/v1/maintenance/MT-081")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "MT-081"
    assert data["vehicle"] == "Yamaha FZ-S FI"
    assert data["cost"] == 2400.0


def test_get_maintenance_not_found():
    response = client.get("/api/v1/maintenance/MT-99999")
    assert response.status_code == 404


def test_create_maintenance_with_damage():
    payload = {
        "vehicle_id": "VH-1038",
        "vehicle": "Royal Enfield Classic 350",
        "registration": "GJ 05 CD 7194",
        "type": "Accident damage",
        "damage_details": "Front fork bend and broken headlight clamp after return inspection.",
        "start": "Oct 30, 2026",
        "expected": "Nov 02, 2026",
        "cost": 4500.0,
        "payment": "Pending",
        "mechanic_name": "Sharma Workshop",
        "notes": "Mechanic ordered genuine OEM headlight assembly.",
    }
    response = client.post("/api/v1/maintenance", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["id"].startswith("MT-")
    assert created["vehicle"] == "Royal Enfield Classic 350"
    assert created["cost"] == 4500.0
    assert created["status"] == "Ongoing"
    assert "Front fork bend" in created["damage_details"]

    # Verify retrieval
    get_res = client.get(f"/api/v1/maintenance/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["damage_details"] == created["damage_details"]


def test_complete_maintenance():
    # First create a job
    payload = {
        "vehicle_id": "VH-1018",
        "vehicle": "Bajaj Pulsar N160",
        "type": "Clutch cable replacement",
        "damage": "Hard clutch pull reported by rider",
        "start": "Oct 30, 2026",
        "amount": 420.0,
    }
    res = client.post("/api/v1/maintenance", json=payload)
    assert res.status_code == 201
    m_id = res.json()["id"]

    # Complete it
    comp_res = client.post(f"/api/v1/maintenance/{m_id}/complete")
    assert comp_res.status_code == 200
    data = comp_res.json()
    assert data["status"] == "Completed"


def test_update_vehicle_review_status():
    payload = {
        "vehicle_id": "VH-1038",
        "status": "Under Review",
        "notes": "Bike returned from 2-day rental, awaiting mechanic inspection.",
    }
    response = client.post("/api/v1/maintenance/vehicle-status", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["vehicle_id"] == "VH-1038"
    assert data["status"] == "Under Review"


def test_maintenance_stats():
    response = client.get("/api/v1/maintenance/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "open_jobs" in stats
    assert "completed_jobs" in stats
    assert "total_cost" in stats
    assert stats["total_jobs"] >= 4
