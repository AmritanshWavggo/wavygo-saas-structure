from __future__ import annotations

import sys

import mongomock
import pytest
from bson import ObjectId

from app.db import mongodb
from scripts import migrate_vehicle_tenant


def test_required_tenant_indexes_are_created(monkeypatch):
    database = mongomock.MongoClient().wavygo_test
    monkeypatch.setattr(mongodb, "get_database", lambda: database)
    mongodb.ensure_indexes()
    assert database.tenants.index_information()["uq_tenant_slug"]["unique"] is True
    assert database.users.index_information()["uq_user_email"]["unique"] is True
    vehicle_index = database.vehicles.index_information()["uq_vehicle_tenant_registration_active"]
    assert vehicle_index["key"] == [("tenantId", 1), ("registrationNumber", 1)]
    assert vehicle_index["partialFilterExpression"] == {"deletedAt": {"$type": "null"}, "registrationNumber": {"$type": "string"}}

    # Bookings indexes
    booking_indexes = database.bookings.index_information()
    assert booking_indexes["uq_bookings_tenant_number"]["key"] == [("tenantId", 1), ("bookingNumber", 1)]
    assert booking_indexes["uq_bookings_tenant_number"]["unique"] is True
    assert booking_indexes["ix_bookings_overlap_scan"]["key"] == [
        ("tenantId", 1), ("vehicleId", 1), ("status", 1), ("startDate", 1), ("endDate", 1)
    ]
    assert booking_indexes["ix_bookings_tenant_customer"]["key"] == [("tenantId", 1), ("customerId", 1)]
    assert booking_indexes["ix_bookings_tenant_deleted_status_created"]["key"] == [
        ("tenantId", 1), ("deletedAt", 1), ("status", 1), ("createdAt", -1)
    ]
    assert booking_indexes["uq_bookings_tenant_vehicle_active"]["key"] == [("tenantId", 1), ("vehicleId", 1)]
    assert booking_indexes["uq_bookings_tenant_vehicle_active"]["unique"] is True
    assert booking_indexes["uq_bookings_tenant_vehicle_active"]["partialFilterExpression"] == {
        "status": "Active", "deletedAt": {"$type": "null"}
    }


def test_migration_dry_run_aborts_when_target_tenant_has_duplicate_plate(monkeypatch):
    client = mongomock.MongoClient()
    database = client.wavygo_test
    tenant_id, owner_id = ObjectId(), ObjectId()
    database.users.insert_one({"_id": owner_id, "tenantId": tenant_id, "role": "owner", "isActive": True})
    database.vehicles.insert_many([
        {"_id": ObjectId(), "registrationNumber": "GJ05AB4821"},
        {"_id": ObjectId(), "tenantId": tenant_id, "deletedAt": None, "registrationNumber": "GJ05AB4821"},
    ])
    monkeypatch.setattr(migrate_vehicle_tenant, "MongoClient", lambda _: client)
    monkeypatch.setattr(migrate_vehicle_tenant.settings, "mongodb_uri", "mongodb://test")
    monkeypatch.setattr(migrate_vehicle_tenant.settings, "mongodb_database", "wavygo_test")
    monkeypatch.setattr(sys, "argv", ["migrate_vehicle_tenant.py", "--tenant-id", str(tenant_id), "--dry-run"])
    with pytest.raises(SystemExit, match="1"):
        migrate_vehicle_tenant.main()


def test_index_failure_raises_runtime_error_and_stops_startup(monkeypatch):
    database = mongomock.MongoClient().wavygo_test
    monkeypatch.setattr(mongodb, "get_database", lambda: database)

    def fake_create_index(*args, **kwargs):
        raise mongodb.DuplicateKeyError("E11000 duplicate key error")

    monkeypatch.setattr(database["vehicles"], "create_index", fake_create_index)
    with pytest.raises(RuntimeError, match="Database indexes could not be created; refusing to start.") as exc_info:
        mongodb.ensure_indexes()
    assert isinstance(exc_info.value.__cause__, mongodb.DuplicateKeyError)

