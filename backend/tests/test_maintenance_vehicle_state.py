import mongomock
import pytest
from fastapi import HTTPException

from app.modules.maintenance.schemas import MaintenanceCreate, MaintenanceUpdate
from app.modules.maintenance.service import maintenance_service
from app.modules.bookings.schemas import OfflineBookingCreate
from app.modules.bookings.service import booking_service


@pytest.fixture
def state_db(monkeypatch):
    db = mongomock.MongoClient()["maintenance_state"]
    monkeypatch.setattr("app.modules.maintenance.service.get_database", lambda: db)
    monkeypatch.setattr("app.modules.bookings.service.get_database", lambda: db)
    maintenance_service._transactions_supported = None
    return db, "tenant-a"


def payload():
    return MaintenanceCreate(vehicle_id="VH-1", vehicle="Bike", start="2026-11-01", expected="2026-11-02")


def vehicle(db, tenant, state="Available"):
    db["vehicles"].insert_one({"_id": "VH-1", "id": "VH-1", "tenantId": tenant, "availability": state, "fleetAvailability": state})


def booking_payload(start="2026-11-01", end="2026-11-02"):
    return {
        "vehicle": {"vehicle_id": "VH-1", "vehicle_name": "Bike", "price_per_day": 100.0},
        "customer": {"name": "Test Customer", "phone": "9876543210", "aadhaar": "123456789012"},
        "rental": {"start_date": start, "end_date": end, "pickup_location": "Garage"},
        "payment": {},
    }


def test_start_and_complete_maintenance_keeps_fields_synced(state_db):
    db, tenant = state_db
    vehicle(db, tenant)
    created = maintenance_service.create_maintenance(payload(), tenant)
    assert db["vehicles"].find_one({"id": "VH-1"})["availability"] == "Maintenance"
    assert db["vehicles"].find_one({"id": "VH-1"})["fleetAvailability"] == "Maintenance"
    maintenance_service.complete_maintenance(created.id)
    assert db["vehicles"].find_one({"id": "VH-1"})["availability"] == "Available"
    assert db["vehicles"].find_one({"id": "VH-1"})["fleetAvailability"] == "Available"


def test_rental_and_confirmed_conflicts_leave_vehicle_unchanged(state_db):
    db, tenant = state_db
    vehicle(db, tenant, "Rented")
    db["bookings"].insert_one({"id": "BK-1", "tenant_id": tenant, "status": "Active", "vehicle_details": {"id": "VH-1"}, "vehicle": "Bike"})
    with pytest.raises(HTTPException) as active:
        maintenance_service.create_maintenance(payload(), tenant)
    assert active.value.status_code == 409
    assert db["vehicles"].find_one({"id": "VH-1"})["availability"] == "Rented"
    db["bookings"].delete_many({})
    db["vehicles"].update_one({"id": "VH-1"}, {"$set": {"availability": "Available", "fleetAvailability": "Available"}})
    db["bookings"].insert_one({"id": "BK-2", "tenant_id": tenant, "status": "Confirmed", "vehicle_details": {"id": "VH-1"}, "vehicle": "Bike", "dates": "Nov 01 – Nov 02", "rental_details": {"start_date": "2026-11-01", "end_date": "2026-11-02"}})
    with pytest.raises(HTTPException) as future:
        maintenance_service.create_maintenance(payload(), tenant)
    assert "BK-2" in future.value.detail and "Nov 01" in future.value.detail


def test_completion_with_active_booking_keeps_rented_and_update_path_matches(state_db):
    db, tenant = state_db
    vehicle(db, tenant)
    created = maintenance_service.create_maintenance(payload(), tenant)
    db["bookings"].insert_one({"id": "BK-3", "tenant_id": tenant, "status": "Active", "vehicle_details": {"id": "VH-1"}, "vehicle": "Bike"})
    maintenance_service.update_maintenance(created.id, MaintenanceUpdate(status="Completed"), tenant)
    result = db["vehicles"].find_one({"id": "VH-1"})
    assert result["availability"] == result["fleetAvailability"] == "Rented"


def test_insert_failure_compensates_vehicle_state(state_db, monkeypatch):
    db, tenant = state_db
    vehicle(db, tenant, "Available")
    original = db["maintenance"].replace_one
    monkeypatch.setattr(db["maintenance"], "replace_one", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("insert failed")))
    with pytest.raises(RuntimeError):
        maintenance_service.create_maintenance(payload(), tenant)
    result = db["vehicles"].find_one({"id": "VH-1"})
    assert result["availability"] == result["fleetAvailability"] == "Available"


def test_booking_rejects_maintenance_and_overlapping_windows_but_allows_non_overlapping(state_db):
    db, tenant = state_db
    vehicle(db, tenant, "Maintenance")

    with pytest.raises(HTTPException) as stored_maintenance:
        booking_service.create_offline_booking(OfflineBookingCreate.model_validate(booking_payload()), tenant)
    assert stored_maintenance.value.status_code == 409

    db["vehicles"].update_one({"id": "VH-1"}, {"$set": {"availability": "Available", "fleetAvailability": "Available"}})
    db["maintenance"].insert_one({
        "id": "MT-window", "tenant_id": tenant, "vehicle_id": "VH-1", "vehicle": "Bike",
        "start": "2026-11-05", "expected": "2026-11-07", "status": "Ongoing",
    })
    with pytest.raises(HTTPException) as overlap:
        booking_service.assert_vehicle_bookable("VH-1", "2026-11-06", "2026-11-08", tenant, "Bike")
    assert overlap.value.status_code == 409
    assert "overlapping maintenance" in overlap.value.detail

    booking_service.assert_vehicle_bookable("VH-1", "2026-11-08", "2026-11-09", tenant, "Bike")


def test_guarded_fallback_rejects_a_state_change_between_check_and_claim(state_db, monkeypatch):
    db, tenant = state_db
    vehicle(db, tenant)
    original = db["vehicles"].find_one_and_update

    def flip_to_rented(*args, **kwargs):
        db["vehicles"].update_one({"id": "VH-1"}, {"$set": {"availability": "Rented", "fleetAvailability": "Rented"}})
        return original(*args, **kwargs)

    monkeypatch.setattr(db["vehicles"], "find_one_and_update", flip_to_rented)
    with pytest.raises(HTTPException) as conflict:
        maintenance_service.create_maintenance(payload(), tenant)
    assert conflict.value.status_code == 409
    assert db["maintenance"].count_documents({}) == 0
    vehicle_after = db["vehicles"].find_one({"id": "VH-1"})
    assert vehicle_after["availability"] == vehicle_after["fleetAvailability"] == "Rented"
