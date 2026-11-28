from datetime import datetime, timedelta, timezone

from bson import ObjectId
import mongomock
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.modules.bookings import router as booking_router
from app.modules.bookings.schemas import LifecycleActionRequest, OfflineBookingCreate, OfflineBookingUpdate, ReturnBookingRequest
from app.modules.bookings.service import booking_service
from app.modules.payments.schemas import PaymentCreate
from app.modules.payments.service import payment_service


@pytest.fixture
def lifecycle_db(monkeypatch):
    db = mongomock.MongoClient()["booking_lifecycle"]
    db["payments"].create_index(
        [("tenant_id", 1), ("idempotency_key", 1)], unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string", "$gt": ""}},
    )
    db["payments"].create_index(
        [("tenant_id", 1), ("booking", 1), ("transaction_reference", 1)], unique=True,
        partialFilterExpression={"transaction_reference": {"$type": "string", "$gt": ""}},
    )
    monkeypatch.setattr("app.modules.bookings.service.get_database", lambda: db)
    monkeypatch.setattr("app.modules.payments.service.get_database", lambda: db)
    monkeypatch.setattr("app.modules.notifications.service.get_database", lambda: db)
    return db, str(ObjectId())


def add_booking(db, tenant_id, booking_id="BK-LIFE", status="Confirmed", paid=0.0, total=1000.0, end_date="2026-11-01"):
    now = datetime.now(timezone.utc).isoformat()
    db["bookings"].insert_one({
        "_id": booking_id, "id": booking_id, "tenant_id": tenant_id, "vendor_id": tenant_id,
        "customer": "Lifecycle Customer", "vehicle": "Lifecycle Bike", "status": status,
        "paid": paid, "pending": total - paid, "total_amount": total, "finalTotalAmount": total,
        "base_amount": total, "add_on_amount": 0.0, "service_fee": 0.0, "discount_amount": 0.0,
        "deposit_amount": 0.0, "rental_days": 1, "dates": "Nov 01 – Nov 01", "type": "Offline",
        "vehicle_details": {"id": "VH-LIFE", "name": "Lifecycle Bike", "price_per_day": 100.0},
        "customer_details": {"id": "", "name": "Lifecycle Customer", "phone": "9999999999"},
        "rental_details": {"start_date": "2026-10-31", "end_date": end_date, "return_time": "10:00"},
        "payment_details": {"transactions": []}, "additionalCharges": [], "created_at": now, "updated_at": now,
    })
    if not db["vehicles"].find_one({"id": "VH-LIFE"}):
        db["vehicles"].insert_one({"_id": "VH-LIFE", "id": "VH-LIFE", "tenantId": tenant_id, "fleetAvailability": "Available", "availability": "Available"})


def test_full_lifecycle_and_payment_status_is_independent(lifecycle_db):
    db, tenant = lifecycle_db
    add_booking(db, tenant)
    rented = booking_service.handover_booking("BK-LIFE", LifecycleActionRequest(occurred_at=datetime(2026, 11, 1, 4, tzinfo=timezone.utc)), tenant)
    assert rented.status == "Active" and rented.payment_status == "Unpaid"
    returned = booking_service.return_booking("BK-LIFE", ReturnBookingRequest(occurred_at=datetime(2026, 11, 1, 4, 30, tzinfo=timezone.utc), extra_charges=50, extra_charge_reason="Fuel"), tenant)
    assert returned.status == "Returned" and returned.total_amount == 1050.0
    completed = booking_service.complete_booking("BK-LIFE", LifecycleActionRequest(), tenant)
    assert completed.status == "Completed" and completed.outstanding == 1050.0
    payment_service.record_payment(PaymentCreate(booking_id="BK-LIFE", amount=1050, method="Cash", idempotency_key="after-complete"), tenant)
    assert db["bookings"].find_one({"id": "BK-LIFE"})["paid"] == 1050.0
    assert db["vehicles"].find_one({"id": "VH-LIFE"})["fleetAvailability"] == "Available"


def test_invalid_repeated_cancelled_and_cross_tenant_transitions(lifecycle_db):
    db, tenant = lifecycle_db
    add_booking(db, tenant)
    with pytest.raises(HTTPException) as invalid:
        booking_service.return_booking("BK-LIFE", ReturnBookingRequest(), tenant)
    assert invalid.value.status_code == 409
    booking_service.handover_booking("BK-LIFE", LifecycleActionRequest(), tenant)
    with pytest.raises(HTTPException) as repeated:
        booking_service.handover_booking("BK-LIFE", LifecycleActionRequest(), tenant)
    assert repeated.value.status_code == 409
    with pytest.raises(HTTPException) as other_tenant:
        booking_service.return_booking("BK-LIFE", ReturnBookingRequest(), str(ObjectId()))
    assert other_tenant.value.status_code == 404
    booking_service.cancel_booking("BK-LIFE", tenant)
    with pytest.raises(HTTPException) as cancelled:
        booking_service.handover_booking("BK-LIFE", LifecycleActionRequest(), tenant)
    assert cancelled.value.status_code == 409
    db["bookings"].update_one({"id": "BK-LIFE"}, {"$set": {"status": "Returned"}})
    with pytest.raises(HTTPException) as cannot_cancel_returned:
        booking_service.cancel_booking("BK-LIFE", tenant)
    assert cannot_cancel_returned.value.status_code == 409


def test_patch_rejects_lifecycle_statuses():
    request = Request({"type": "http", "method": "PATCH", "path": "/", "headers": []})
    with pytest.raises(HTTPException) as error:
        booking_router.update_offline_booking("BK-LIFE", OfflineBookingUpdate(status="Active"), request)
    assert error.value.status_code == 409


def test_two_bookings_cannot_handover_same_vehicle(lifecycle_db):
    db, tenant = lifecycle_db
    add_booking(db, tenant, "BK-ONE")
    add_booking(db, tenant, "BK-TWO")
    booking_service.handover_booking("BK-ONE", LifecycleActionRequest(), tenant)
    with pytest.raises(HTTPException) as conflict:
        booking_service.handover_booking("BK-TWO", LifecycleActionRequest(), tenant)
    assert conflict.value.status_code == 409


def test_legacy_active_can_return_and_late_charge_is_paise_safe(lifecycle_db):
    db, tenant = lifecycle_db
    add_booking(db, tenant, status="Active", end_date="2026-01-01")
    returned = booking_service.return_booking(
        "BK-LIFE", ReturnBookingRequest(occurred_at=datetime(2026, 1, 3, 10, 1, tzinfo=timezone.utc)), tenant,
    )
    assert returned.status == "Returned"
    assert returned.total_amount == 1300.0
    assert returned.additionalCharges[0]["type"] == "late"


def test_lifecycle_respects_open_maintenance_vehicle_state(lifecycle_db):
    db, tenant = lifecycle_db
    add_booking(db, tenant)
    db["maintenance"].insert_one({
        "id": "MT-LIFE", "tenant_id": tenant, "vehicle_id": "VH-LIFE", "status": "Ongoing",
    })
    with pytest.raises(HTTPException) as handover:
        booking_service.handover_booking("BK-LIFE", LifecycleActionRequest(), tenant)
    assert handover.value.status_code == 409

    db["maintenance"].delete_many({})
    booking_service.handover_booking("BK-LIFE", LifecycleActionRequest(), tenant)
    db["maintenance"].insert_one({
        "id": "MT-LIFE", "tenant_id": tenant, "vehicle_id": "VH-LIFE", "status": "Ongoing",
    })
    booking_service.return_booking("BK-LIFE", ReturnBookingRequest(), tenant)
    assert db["vehicles"].find_one({"id": "VH-LIFE"})["availability"] == "Maintenance"
    booking_service.complete_booking("BK-LIFE", LifecycleActionRequest(), tenant)
    vehicle = db["vehicles"].find_one({"id": "VH-LIFE"})
    assert vehicle["availability"] == vehicle["fleetAvailability"] == "Maintenance"


def test_return_never_reduces_total_below_paid_and_preserves_history(lifecycle_db):
    db, tenant = lifecycle_db
    add_booking(db, tenant, status="Active", paid=900.0)
    db["bookings"].update_one({"id": "BK-LIFE"}, {"$push": {"payment_details.transactions": {"id": "TX-OLD", "amount": 900.0}}})
    returned = booking_service.return_booking("BK-LIFE", ReturnBookingRequest(occurred_at=datetime(2026, 11, 1, 4, 30, tzinfo=timezone.utc), extra_charges=25, extra_charge_reason="Damage"), tenant)
    assert returned.total_amount == 1025.0 and returned.paid == 900.0
    assert db["bookings"].find_one({"id": "BK-LIFE"})["payment_details"]["transactions"][0]["id"] == "TX-OLD"


def test_creation_records_advance_once_and_requires_non_cash_reference(lifecycle_db):
    db, tenant = lifecycle_db
    payload = OfflineBookingCreate.model_validate({
        "vehicle": {"vehicle_id": "VH-CREATE", "vehicle_name": "Create Bike", "price_per_day": 500},
        "customer": {"name": "Advance Customer", "phone": "9999999999", "aadhaar": "123456789012"},
        "rental": {"start_date": "2026-11-01", "end_date": "2026-11-02", "pickup_location": "Desk"},
        "payment": {"method": "Cash", "paid_amount": 100},
    })
    created = booking_service.create_offline_booking(payload, tenant)
    assert created.status == "Confirmed" and created.paid == 100.0
    assert db["payments"].count_documents({"booking": created.id}) == 1
    customer = db["customers"].find_one({"name": "Advance Customer"})
    assert customer["paid"] == 100.0
    assert customer["pending"] == created.total_amount - 100.0
    missing_reference = OfflineBookingCreate.model_validate({
        "vehicle": {"vehicle_id": "VH-CREATE-2", "vehicle_name": "Create Bike", "price_per_day": 500},
        "customer": {"name": "Reference Customer", "phone": "9888888888", "aadhaar": "123456789012"},
        "rental": {"start_date": "2026-11-01", "end_date": "2026-11-02", "pickup_location": "Desk"},
        "payment": {"method": "UPI", "paid_amount": 100},
    })
    with pytest.raises(HTTPException) as error:
        booking_service.create_offline_booking(missing_reference, tenant)
    assert error.value.status_code == 422


def test_returned_vehicle_can_be_handed_over_for_new_booking(lifecycle_db):
    db, tenant = lifecycle_db
    # First booking: Handover, then return (vehicle moves to 'Under Review', booking is 'Returned')
    add_booking(db, tenant, booking_id="BK-PAST")
    booking_service.handover_booking("BK-PAST", LifecycleActionRequest(), tenant)
    booking_service.return_booking("BK-PAST", ReturnBookingRequest(), tenant)
    assert db["bookings"].find_one({"id": "BK-PAST"})["status"] == "Returned"
    assert db["vehicles"].find_one({"id": "VH-LIFE"})["availability"] == "Under Review"

    # Second booking on the same vehicle: Handover must succeed and not be blocked by BK-PAST
    add_booking(db, tenant, booking_id="BK-NEXT")
    next_booking = booking_service.handover_booking("BK-NEXT", LifecycleActionRequest(), tenant)
    assert next_booking.status == "Active"
    assert db["vehicles"].find_one({"id": "VH-LIFE"})["availability"] == "Rented"

