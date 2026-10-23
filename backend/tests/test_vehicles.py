from __future__ import annotations

from io import BytesIO
import inspect

import pytest
from bson import ObjectId
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.modules.auth.deps import get_current_tenant
from app.modules.vehicles import router
from app.modules.vehicles.schemas import ShowOnWavygoSchema
from app.modules.vehicles.upload_middleware import MAX_PHOTO_SIZE_BYTES

TENANT = {"tenant_id": "dev_tenant", "role": "owner"}


def upload_file(content: bytes = b"photo", content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        size=len(content),
        filename="upload.jpg",
        headers=Headers({"content-type": content_type}),
    )


def create(**overrides):
    payload = {
        "tenant": TENANT,
        "make_model": "Honda Activa",
        "registration": "GJ 05 AB 4821",
        "year": 2024,
        "type": "Scooter",
        "fuel": "Petrol",
        "transmission": "Automatic",
        "registration_number": "GJ05AB4821",
        "color": "Blue",
        "engine_capacity": 125,
        "seats": 2,
        "rc_status": "Pending review",
        "trim": None,
        "daily_rate": 500.0,
        "minimum_days": 1,
        "security_deposit": 1000.0,
        "pickup_address": "Surat",
        "pickup_lat": None,
        "pickup_lng": None,
        "pickup_notes": None,
        "show_on_wavygo": False,
        "fleet_availability": "Available",
        "photos": [],
        "documents": [],
        "document_types": [],
    }
    payload.update(overrides)
    return router.create_vehicle(**payload)


def update(vehicle_id: str, **overrides):
    payload = {
        "vehicle_id": vehicle_id,
        "tenant": TENANT,
        "make_model": None, "registration": None, "year": None, "type": None, "fuel": None,
        "transmission": None, "registration_number": None, "color": None, "engine_capacity": None,
        "seats": None, "rc_status": None, "trim": None, "daily_rate": None,
        "minimum_days": None, "security_deposit": None, "pickup_address": None, "pickup_lat": None,
        "pickup_lng": None, "pickup_notes": None, "show_on_wavygo": None,
        "fleet_availability": None, "new_photos": [], "new_documents": [],
        "new_document_types": [], "remove_photo_ids": [], "remove_document_ids": [],
    }
    payload.update(overrides)
    return router.update_vehicle(**payload)


def stored_id(store) -> str:
    return str(store.vehicles.documents[0]["_id"])


def test_create_success_and_validation(vehicle_store):
    created = create(photos=[upload_file()], documents=[upload_file(b"pdf", "application/pdf")], document_types=["RC"], show_on_wavygo=True)
    assert created["price"] == created["dailyRate"] == 500.0
    assert created["status"] == "Online"
    assert created["documents"][0]["resourceType"] == "raw"

    with pytest.raises(HTTPException) as error:
        create(make_model="", registration_number=None)
    assert error.value.status_code == 422


def test_create_duplicate_invalid_file_and_cleanup_failures(vehicle_store, monkeypatch):
    create()
    with pytest.raises(HTTPException) as duplicate:
        create()
    assert duplicate.value.status_code == 409

    with pytest.raises(HTTPException) as invalid_file:
        create(registration_number="GJ05AB9999", photos=[upload_file(b"x", "text/plain")])
    assert invalid_file.value.status_code == 422

    calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("upload failed")
        return {"url": "https://cdn.test/one", "public_id": "first"}
    monkeypatch.setattr(router.cloudinary_service, "upload_file", fail_second)
    with pytest.raises(HTTPException) as upload_failure:
        create(registration_number="GJ05AB9999", photos=[upload_file(), upload_file()])
    assert upload_failure.value.status_code == 502
    assert ("first", "image") in vehicle_store.deletes

    monkeypatch.setattr(router.cloudinary_service, "upload_file", lambda *a, **k: {"url": "https://cdn.test/db", "public_id": "db-file"})
    vehicle_store.vehicles.fail_insert = True
    with pytest.raises(HTTPException) as db_failure:
        create(registration_number="GJ05AB8888", photos=[upload_file()])
    assert db_failure.value.status_code == 500
    assert ("db-file", "image") in vehicle_store.deletes


def test_get_found_not_found_and_invalid_id(vehicle_store):
    create()
    assert router.get_vehicle(stored_id(vehicle_store), TENANT)["name"] == "Honda Activa"
    for vehicle_id in (str(ObjectId()), "not-an-object-id"):
        with pytest.raises(HTTPException) as error:
            router.get_vehicle(vehicle_id, TENANT)
        assert error.value.status_code == 404


def test_update_media_and_duplicate_rc(vehicle_store):
    create(photos=[upload_file()], documents=[upload_file(b"doc", "application/pdf")], document_types=["RC"])
    vehicle_id = stored_id(vehicle_store)
    original = vehicle_store.vehicles.documents[0]
    original["photos"][0]["publicId"] = "old-photo"
    original["documents"][0]["publicId"] = "old-doc"
    response = update(vehicle_id, new_photos=[upload_file()], new_documents=[upload_file(b"next", "application/pdf")], new_document_types=["Insurance"], remove_photo_ids=["old-photo"], remove_document_ids=["old-doc"], daily_rate=650.0)
    assert response["price"] == response["dailyRate"] == 650.0
    assert ("old-photo", "image") in vehicle_store.deletes
    assert ("old-doc", "raw") in vehicle_store.deletes

    create(registration_number="GJ05AB7777")
    with pytest.raises(HTTPException) as duplicate:
        update(vehicle_id, registration_number="GJ05AB7777")
    assert duplicate.value.status_code == 409


def test_update_does_not_delete_removed_assets_when_db_write_fails(vehicle_store):
    create(photos=[upload_file()])
    vehicle_id = stored_id(vehicle_store)
    vehicle_store.vehicles.documents[0]["photos"][0]["publicId"] = "keep-until-db-success"
    vehicle_store.vehicles.fail_update = True
    with pytest.raises(HTTPException) as error:
        update(vehicle_id, remove_photo_ids=["keep-until-db-success"])
    assert error.value.status_code == 500
    assert ("keep-until-db-success", "image") not in vehicle_store.deletes


def test_delete_booking_protection_and_cloudinary_cleanup(vehicle_store):
    create(photos=[upload_file()])
    vehicle_id = stored_id(vehicle_store)
    vehicle_store.bookings.documents.append({"_id": ObjectId(), "vehicleId": vehicle_id})
    with pytest.raises(HTTPException) as blocked:
        router.delete_vehicle(vehicle_id, TENANT)
    assert blocked.value.status_code == 409
    vehicle_store.bookings.documents.clear()
    assert router.delete_vehicle(vehicle_id, TENANT)["id"] == vehicle_id
    assert ("asset-1", "image") in vehicle_store.deletes


def test_list_filters_pagination_listing_and_safe_search(vehicle_store):
    create(show_on_wavygo=True, registration_number="GJ05AB1111", make_model="A+B Bike")
    create(show_on_wavygo=False, registration_number="GJ05AB2222", make_model="Second Bike")
    listed = router.list_vehicles(TENANT, search="A+B", type="Scooter", fuel="Petrol", fleet_availability="Available", listing="online", page=1, limit=1)
    assert listed["total"] == 1 and listed["items"][0]["name"] == "A+B Bike"
    offline = router.list_vehicles(TENANT, search=None, type=None, fuel=None, fleet_availability=None, listing="offline", page=1, limit=20)
    assert offline["total"] == 1
    injection = router.list_vehicles(TENANT, search='{"$ne":""}', type=None, fuel=None, fleet_availability=None, listing="all", page=1, limit=20)
    assert injection["total"] == 0


def test_toggle_keeps_availability_and_auth_stub_is_documented(vehicle_store):
    create()
    vehicle_id = stored_id(vehicle_store)
    before = vehicle_store.vehicles.documents[0]["fleetAvailability"]
    toggled = router.toggle_show_on_wavygo(vehicle_id, ShowOnWavygoSchema(showOnWavygo=True), TENANT)
    assert toggled["showOnWavygo"] is True and toggled["status"] == "Online"
    assert toggled["fleetAvailability"] == before
    assert get_current_tenant() == {"tenant_id": "dev_tenant", "role": "owner"}


@pytest.mark.xfail(
    strict=True,
    reason="Vehicle records do not store tenant ownership and route queries do not scope by tenant.",
)
@pytest.mark.parametrize("operation", ["get", "list", "update", "toggle", "delete"])
def test_tenant_b_cannot_access_tenant_a_vehicle(vehicle_store, operation):
    tenant_a = {"tenant_id": "tenant-a", "role": "owner"}
    tenant_b = {"tenant_id": "tenant-b", "role": "owner"}

    created = create(tenant=tenant_a)
    vehicle_id = created["id"]

    if operation == "get":
        with pytest.raises(HTTPException) as error:
            router.get_vehicle(vehicle_id, tenant_b)
        assert error.value.status_code == 404
    elif operation == "list":
        listing = router.list_vehicles(
            tenant_b,
            search=None,
            type=None,
            fuel=None,
            fleet_availability=None,
            listing="all",
            page=1,
            limit=20,
        )
        assert listing["items"] == []
    elif operation == "update":
        with pytest.raises(HTTPException) as error:
            update(vehicle_id, tenant=tenant_b, color="Red")
        assert error.value.status_code == 404
    elif operation == "toggle":
        with pytest.raises(HTTPException) as error:
            router.toggle_show_on_wavygo(
                vehicle_id,
                ShowOnWavygoSchema(showOnWavygo=True),
                tenant_b,
            )
        assert error.value.status_code == 404
    else:
        with pytest.raises(HTTPException) as error:
            router.delete_vehicle(vehicle_id, tenant_b)
        assert error.value.status_code == 404


def test_oversize_photo_is_rejected(vehicle_store):
    with pytest.raises(HTTPException) as error:
        create(
            photos=[upload_file(b"x" * (MAX_PHOTO_SIZE_BYTES + 1))],
        )
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"daily_rate": -1.0},
        {"pickup_lat": 90.1, "pickup_lng": 0.0},
        {"pickup_lat": 0.0, "pickup_lng": 180.1},
    ],
)
def test_invalid_scalar_values_return_422(vehicle_store, overrides):
    with pytest.raises(HTTPException) as error:
        create(**overrides)
    assert error.value.status_code == 422


def test_listing_all_returns_online_and_offline_vehicles(vehicle_store):
    create(show_on_wavygo=True, registration_number="GJ05AB3333")
    create(show_on_wavygo=False, registration_number="GJ05AB4444")

    listed = router.list_vehicles(
        TENANT,
        search=None,
        type=None,
        fuel=None,
        fleet_availability=None,
        listing="all",
        page=1,
        limit=20,
    )

    assert listed["total"] == 2
    assert {item["showOnWavygo"] for item in listed["items"]} == {False, True}


def test_list_limit_declares_a_maximum_page_size(vehicle_store):
    limit = inspect.signature(router.list_vehicles).parameters["limit"].default
    assert any(getattr(constraint, "le", None) == 100 for constraint in limit.metadata)
