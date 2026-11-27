import pytest
import mongomock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.modules.maintenance.schemas import MaintenanceCreate
from app.modules.maintenance.service import maintenance_service

@pytest.fixture(autouse=True)
def isolated_maintenance_db(monkeypatch):
    """Keep these endpoint tests independent of a developer's MongoDB data."""
    db = mongomock.MongoClient()["maintenance_endpoint_tests"]
    db["vehicles"].insert_many([
        {"_id": "VH-1038", "id": "VH-1038", "availability": "Available", "fleetAvailability": "Available"},
        {"_id": "VH-1018", "id": "VH-1018", "availability": "Available", "fleetAvailability": "Available"},
    ])
    monkeypatch.setattr("app.main.create_mongo_client", lambda: None)
    monkeypatch.setattr("app.main.get_database", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.main.ensure_vehicle_indexes", lambda: None)
    monkeypatch.setattr("app.main.ensure_payment_indexes", lambda: None)
    monkeypatch.setattr("app.modules.maintenance.service.get_database", lambda: db)
    maintenance_service._transactions_supported = None
    yield db


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_create_maintenance_still_rejects_an_active_rental(isolated_maintenance_db):
    isolated_maintenance_db["bookings"].insert_one({
        "id": "BK-BLOCKING", "status": "Active", "vehicle_details": {"id": "VH-1038"},
        "vehicle": "Royal Enfield Classic 350", "tenant_id": None,
    })
    payload = MaintenanceCreate(
        vehicle_id="VH-1038", vehicle="Royal Enfield Classic 350", start="2026-10-30",
    )
    with pytest.raises(HTTPException) as response:
        maintenance_service.create_maintenance(payload)
    assert response.value.status_code == 409
    assert response.value.detail == "Vehicle has an active rental"


def test_affected_vehicle_fixtures_allow_create_and_complete_when_unblocked(isolated_maintenance_db):
    created = maintenance_service.create_maintenance(MaintenanceCreate(
        vehicle_id="VH-1038", vehicle="Royal Enfield Classic 350", start="Oct 30, 2026",
        expected="Nov 02, 2026", cost=4500.0, damage_details="Front fork bend",
    ))
    assert created.status == "Ongoing"

    completion = maintenance_service.create_maintenance(MaintenanceCreate(
        vehicle_id="VH-1018", vehicle="Bajaj Pulsar N160", start="Oct 30, 2026", cost=420.0,
    ))
    completed = maintenance_service.complete_maintenance(completion.id)
    assert completed is not None and completed.status == "Completed"


def test_list_maintenance(client):
    response = client.get("/api/v1/maintenance")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    # Default seeded record check (handles both DB seed and in-memory fallback)
    ids = [item["id"] for item in data]
    assert any(m_id in ids for m_id in ["MT-301", "MT-081"])


def test_list_maintenance_status_filter(client):
    response = client.get("/api/v1/maintenance?status=Ongoing")
    assert response.status_code == 200
    data = response.json()
    for item in data:
        assert item["status"] == "Ongoing"


def test_get_maintenance(client):
    response = client.get("/api/v1/maintenance/MT-081")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "MT-081"
    assert data["vehicle"] == "Yamaha FZ-S FI"
    assert data["cost"] == 2400.0


def test_get_maintenance_not_found(client):
    response = client.get("/api/v1/maintenance/MT-99999")
    assert response.status_code == 404


def test_create_maintenance_with_damage(client):
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


def test_complete_maintenance(client):
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


def test_update_vehicle_review_status(client):
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


def test_maintenance_stats(client):
    response = client.get("/api/v1/maintenance/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "open_jobs" in stats
    assert "completed_jobs" in stats
    assert "total_cost" in stats
    assert stats["total_jobs"] >= 4
