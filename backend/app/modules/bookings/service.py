"""
Core domain logic, transaction runner, and concurrency controls for Bookings.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Optional

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.errors import PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
from pymongo.write_concern import WriteConcern

from app.modules.bookings.counters import generate_booking_number
from app.modules.bookings.models import (
    BLOCKING_STATUSES,
    BookingStatus,
    CustomerSnapshot,
    VehicleSnapshot,
)

MAX_BOOKING_DURATION_DAYS = 90
IST = timezone(timedelta(hours=5, minutes=30))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class BookingDomainError(Exception):
    """Base exception for booking domain errors."""
    pass


class BookingValidationError(BookingDomainError):
    """Domain validation error for rental constraints (maps to 422)."""
    pass


class VehicleNotFoundError(BookingDomainError):
    """Vehicle not found or soft-deleted in tenant (maps to 404)."""
    pass


class CustomerNotFoundError(BookingDomainError):
    """Customer not found or soft-deleted in tenant (maps to 404)."""
    pass


class VehicleUnderMaintenanceError(BookingDomainError):
    """Vehicle is under maintenance and cannot be rented (maps to 409)."""
    pass


class VehicleInvalidRateError(BookingDomainError):
    """Vehicle has no configured or valid rate (maps to 409)."""
    pass


class OverlapConflictError(BookingDomainError):
    """Vehicle is already booked for the selected interval (maps to 409)."""
    pass


class BookingTransactionTimeoutError(BookingDomainError):
    """Database transaction failed or timed out (maps to 503)."""
    pass


class BookingNotFoundError(BookingDomainError):
    """Booking not found or soft-deleted in tenant (maps to 404)."""
    pass


class BookingStatusConflictError(BookingDomainError):
    """Booking status transition or CAS update conflict (maps to 409)."""
    pass


TRANSITION_TIMESTAMP_MAP = {
    BookingStatus.confirmed.value: "confirmedAt",
    BookingStatus.active.value: "activatedAt",
    BookingStatus.completed.value: "completedAt",
    BookingStatus.cancelled.value: "cancelledAt",
}


def validate_booking_dates(
    start_date: datetime,
    end_date: datetime,
    now: datetime,
    grace_period_days: int = 1,
) -> None:
    """
    Validate rental interval bounds and constraints:
    - End date must be strictly after start date.
    - Duration cannot exceed 90 days.
    - Start date cannot be before the configured grace period:
      Earliest allowed start = 00:00 IST of the day (today_IST - booking_grace_period_days), converted to UTC.
      Uses the injected clock (now) only; no datetime.now inside the function.
    """
    if end_date <= start_date:
        raise BookingValidationError("End date must be strictly after start date.")

    duration_seconds = (end_date - start_date).total_seconds()
    if duration_seconds > MAX_BOOKING_DURATION_DAYS * 86400:
        raise BookingValidationError("Rental duration cannot exceed 90 days.")

    now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    now_ist = now_utc.astimezone(IST)
    today_ist = now_ist.date()
    target_date_ist = today_ist - timedelta(days=grace_period_days)
    start_of_day_ist = datetime.combine(target_date_ist, time.min, tzinfo=IST)
    earliest_allowed_utc = start_of_day_ist.astimezone(timezone.utc)

    start_utc = start_date if start_date.tzinfo is not None else start_date.replace(tzinfo=timezone.utc)
    if start_utc < earliest_allowed_utc:
        raise BookingValidationError("Booking start date cannot be before the grace window.")


def calculate_billable_days(start_date: datetime, end_date: datetime) -> int:
    """
    Compute rental duration in integer billable days using integer ceil-division.
    Rentals use half-open intervals [start, end).
    Any initiated 24-hour cycle counts as a full day.
    """
    duration_seconds = int((end_date - start_date).total_seconds())
    if duration_seconds <= 0:
        raise BookingValidationError("End date must be strictly after start date.")
    # Integer ceil division: (numerator + denominator - 1) // denominator
    return max(1, (duration_seconds + 86400 - 1) // 86400)


def float_to_paise(val: Any) -> int:
    """Convert monetary float / string representations to integer paise using Decimal."""
    if val is None or val == "":
        return 0
    d = Decimal(str(val))
    return int((d * Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def check_overlap(
    db: Any,
    tenant_id: ObjectId,
    vehicle_id: ObjectId,
    start_date: datetime,
    end_date: datetime,
    exclude_booking_id: Optional[ObjectId] = None,
    buffer_minutes: int = 0,
    session: Optional[ClientSession] = None,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """
    Query for overlapping bookings occupying the vehicle interval [start, end).
    Two intervals [A_start, A_end) and [B_start, B_end) overlap iff:
        A_start < B_end and A_end > B_start

    Rule: An Active booking's effective end is max(endDate, now).
    """
    effective_start = start_date - timedelta(minutes=buffer_minutes)
    effective_end = end_date + timedelta(minutes=buffer_minutes)

    if now is None:
        now = _now_utc()

    if effective_start < now:
        overlap_filter = {
            "$or": [
                {"status": {"$in": ["Pending", "Confirmed"]}, "endDate": {"$gt": effective_start}},
                {"status": "Active"},
            ]
        }
    else:
        overlap_filter = {
            "status": {"$in": list(BLOCKING_STATUSES)},
            "endDate": {"$gt": effective_start},
        }

    query = {
        "tenantId": tenant_id,
        "vehicleId": vehicle_id,
        "deletedAt": None,
        "startDate": {"$lt": effective_end},
        **overlap_filter,
    }
    if exclude_booking_id:
        query["_id"] = {"$ne": exclude_booking_id}

    return db["bookings"].find_one(query, session=session)


def apply_booking_guard(
    db: Any,
    vehicle_oid: ObjectId,
    tenant_id: ObjectId,
    session: Optional[ClientSession] = None,
) -> None:
    """
    Serialization point: atomically increment bookingGuard on the vehicle document.
    Forces write lock on the vehicle, ensuring concurrent transactions serialize.
    """
    update_res = db["vehicles"].update_one(
        {"_id": vehicle_oid, "tenantId": tenant_id, "deletedAt": None},
        {"$inc": {"bookingGuard": 1}},
        session=session,
    )
    if update_res.matched_count == 0:
        raise VehicleNotFoundError("Vehicle not found.")


def execute_in_transaction(
    client: Any,
    callback: Callable[[Optional[ClientSession]], Any],
) -> Any:
    """
    Transaction runner abstraction:
    - Real MongoDB replica set: runs callback inside session.with_transaction with majority concerns.
    - mongomock: executes callback directly without multi-document session.
    """
    if not hasattr(client, "start_session") or type(client).__module__.startswith("mongomock"):
        return callback(None)

    with client.start_session() as session:
        try:
            return session.with_transaction(
                callback,
                read_concern=ReadConcern("majority"),
                write_concern=WriteConcern("majority"),
                read_preference=ReadPreference.PRIMARY,
            )
        except PyMongoError as exc:
            raise BookingTransactionTimeoutError(
                f"Transaction failed or timed out: {exc}"
            ) from exc


def create_booking_guarded(
    client: Any,
    db: Any,
    tenant_id: ObjectId,
    user_id: ObjectId,
    vehicle_oid: ObjectId,
    customer_oid: ObjectId,
    start_date: datetime,
    end_date: datetime,
    pickup_location: str,
    status: BookingStatus,
    discount_paise: int = 0,
    notes: Optional[str] = None,
    grace_period_days: int = 1,
    clock_now: Optional[datetime] = None,
) -> dict:
    """
    Atomic booking creation with write-skew elimination:
    1. Serialization point: $inc bookingGuard on the vehicle document via apply_booking_guard.
    2. Vehicle read & maintenance check inside transaction.
    3. Customer read inside transaction.
    4. Overlap query inside transaction.
    5. Insert booking with frozen rate/vehicle/customer snapshots.
    """
    now = clock_now if clock_now is not None else _now_utc()
    validate_booking_dates(
        start_date=start_date,
        end_date=end_date,
        now=now,
        grace_period_days=grace_period_days,
    )
    booking_number = generate_booking_number(db, tenant_id, year=start_date.year)
    billable_days = calculate_billable_days(start_date, end_date)

    created_booking_doc: dict[str, Any] = {}

    def transaction_callback(session: Optional[ClientSession]) -> None:
        # Step 1: Guard $inc on vehicle (Serialization Point)
        apply_booking_guard(db, vehicle_oid, tenant_id, session=session)

        # Step 2: Vehicle read & maintenance check inside transaction
        vehicle = db["vehicles"].find_one(
            {"_id": vehicle_oid, "tenantId": tenant_id, "deletedAt": None},
            session=session,
        )
        if not vehicle:
            raise VehicleNotFoundError("Vehicle not found.")

        if vehicle.get("availability") == "Maintenance":
            raise VehicleUnderMaintenanceError("Vehicle is currently under maintenance.")

        # Rate guard: snapshot must never silently use 0 or missing rate
        daily_rate_raw = vehicle.get("dailyRate") or vehicle.get("price")
        if daily_rate_raw is None or daily_rate_raw <= 0:
            raise VehicleInvalidRateError("Vehicle has no valid daily rate.")

        daily_rate_paise = float_to_paise(daily_rate_raw)
        if daily_rate_paise <= 0:
            raise VehicleInvalidRateError("Vehicle has no valid daily rate.")

        # Step 3: Customer read inside transaction
        customer = db["customers"].find_one(
            {"_id": customer_oid, "tenantId": tenant_id, "deletedAt": None},
            session=session,
        )
        if not customer:
            raise CustomerNotFoundError("Customer not found.")

        # Step 4: Overlap query inside transaction
        conflict = check_overlap(
            db,
            tenant_id,
            vehicle_oid,
            start_date,
            end_date,
            buffer_minutes=0,
            session=session,
        )
        if conflict:
            raise OverlapConflictError("Vehicle is already booked for the selected rental period.")

        # Financial computations (paise minor units via Decimal)
        deposit_paise = float_to_paise(vehicle.get("securityDeposit"))
        base_amount_paise = billable_days * daily_rate_paise

        if discount_paise > base_amount_paise:
            raise BookingValidationError("Discount cannot exceed base rental amount.")

        total_amount_paise = base_amount_paise - discount_paise

        # Build snapshots
        vehicle_snapshot = {
            "name": vehicle.get("name", ""),
            "registration": vehicle.get("registration", ""),
            "registrationNumber": vehicle.get("registrationNumber") or vehicle.get("registration", "").replace(" ", "").upper(),
            "type": vehicle.get("type"),
        }
        customer_snapshot = {
            "name": customer.get("name", ""),
            "phone": customer.get("phone", ""),
            "email": customer.get("email"),
        }

        # Step 5: Insert booking inside transaction
        doc = {
            "tenantId": tenant_id,
            "bookingNumber": booking_number,
            "customerId": customer_oid,
            "vehicleId": vehicle_oid,
            "startDate": start_date,
            "endDate": end_date,
            "pickupLocation": pickup_location,
            "status": status.value,
            "currency": "INR",
            "dailyRatePaise": daily_rate_paise,
            "billableDays": billable_days,
            "baseAmountPaise": base_amount_paise,
            "discountPaise": discount_paise,
            "securityDepositPaise": deposit_paise,
            "totalAmountPaise": total_amount_paise,
            "vehicleSnapshot": vehicle_snapshot,
            "customerSnapshot": customer_snapshot,
            "notes": notes,
            "createdBy": user_id,
            "createdAt": now,
            "updatedAt": now,
            "deletedAt": None,
        }
        res = db["bookings"].insert_one(doc, session=session)
        doc["_id"] = res.inserted_id
        created_booking_doc.update(doc)

    execute_in_transaction(client, transaction_callback)
    return created_booking_doc


def derive_vehicle_availability(vehicle_doc: dict, db: Any, tenant_id: ObjectId) -> str:
    """
    Derive dynamic vehicle availability on read:
    - If stored availability is 'Maintenance', vehicle is 'Maintenance'.
    - If vehicle has an Active booking (with deletedAt == None), vehicle is 'Rented'.
    - Otherwise, vehicle is 'Available'.
    """
    if (
        vehicle_doc.get("availability") == "Maintenance"
        or vehicle_doc.get("fleetAvailability") == "Maintenance"
    ):
        return "Maintenance"

    v_id = vehicle_doc["_id"] if "_id" in vehicle_doc else ObjectId(vehicle_doc["id"])
    has_active_booking = db["bookings"].find_one(
        {
            "tenantId": tenant_id,
            "vehicleId": v_id,
            "status": BookingStatus.active.value,
            "deletedAt": None,
        }
    )
    if has_active_booking:
        return "Rented"

    return "Available"


def transition_booking_status(
    db: Any,
    tenant_id: ObjectId,
    booking_id: ObjectId,
    target_status: BookingStatus,
    user_role: str,
    cancel_reason: Optional[str] = None,
    clock_now: Optional[datetime] = None,
) -> dict:
    """
    Atomic status transition with CAS (compare-and-set) update and role permissions:
    - Allowed transitions:
      Pending -> Confirmed, Cancelled
      Confirmed -> Active, Cancelled
      Active -> Completed
    - Roles:
      Staff cannot cancel Confirmed bookings (Owner/Manager only).
      Staff may confirm, activate, complete, and cancel Pending.
    - Confirmed -> Active is refused (409) if the vehicle already has an Active booking.
    - Uses explicit timestamp map:
      Confirmed -> confirmedAt, Active -> activatedAt, Completed -> completedAt, Cancelled -> cancelledAt.
      Computes `now` once per update.
    """
    now = clock_now if clock_now is not None else _now_utc()
    tgt = target_status.value

    booking = db["bookings"].find_one({"_id": booking_id, "tenantId": tenant_id, "deletedAt": None})
    if not booking:
        raise BookingNotFoundError("Booking not found.")

    curr = booking["status"]

    if curr in [BookingStatus.completed.value, BookingStatus.cancelled.value, BookingStatus.no_show.value]:
        raise BookingStatusConflictError(f"Cannot transition terminal booking from '{curr}' to '{tgt}'.")

    allowed_transitions = {
        BookingStatus.pending.value: [BookingStatus.confirmed.value, BookingStatus.cancelled.value],
        BookingStatus.confirmed.value: [BookingStatus.active.value, BookingStatus.cancelled.value],
        BookingStatus.active.value: [BookingStatus.completed.value],
    }

    if tgt not in allowed_transitions.get(curr, []):
        raise BookingStatusConflictError(f"Invalid status transition from '{curr}' to '{tgt}'.")

    # Role checks: Staff cannot cancel a Confirmed booking
    if curr == BookingStatus.confirmed.value and tgt == BookingStatus.cancelled.value:
        if user_role not in ["owner", "manager"]:
            raise BookingValidationError("Staff members cannot cancel confirmed bookings.")

    # Confirmed -> Active check: vehicle cannot already have an Active booking
    if tgt == BookingStatus.active.value:
        active_existing = db["bookings"].find_one(
            {
                "tenantId": tenant_id,
                "vehicleId": booking["vehicleId"],
                "status": BookingStatus.active.value,
                "deletedAt": None,
                "_id": {"$ne": booking_id},
            }
        )
        if active_existing:
            raise OverlapConflictError("Vehicle already has an active booking in progress.")

    ts_field = TRANSITION_TIMESTAMP_MAP.get(tgt)
    update_fields: dict[str, Any] = {
        "status": tgt,
        "updatedAt": now,
    }
    if ts_field:
        update_fields[ts_field] = now
    if tgt == BookingStatus.cancelled.value and cancel_reason:
        update_fields["cancelReason"] = cancel_reason

    # Compare-and-Set atomic update
    res = db["bookings"].update_one(
        {
            "_id": booking_id,
            "tenantId": tenant_id,
            "status": curr,
            "deletedAt": None,
        },
        {"$set": update_fields},
    )
    if res.matched_count == 0:
        latest = db["bookings"].find_one({"_id": booking_id, "tenantId": tenant_id, "deletedAt": None})
        if not latest:
            raise BookingNotFoundError("Booking not found.")
        raise BookingStatusConflictError(f"Booking was modified concurrently and is no longer '{curr}'.")

    return db["bookings"].find_one({"_id": booking_id})


def update_booking_guarded(
    client: Any,
    db: Any,
    tenant_id: ObjectId,
    booking_id: ObjectId,
    user_role: str,
    customer_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    pickup_location: Optional[str] = None,
    discount_paise: Optional[int] = None,
    notes: Optional[str] = None,
    grace_period_days: int = 1,
    clock_now: Optional[datetime] = None,
) -> dict:
    """
    Guarded booking update with CAS check:
    - Core fields (dates, vehicleId, customerId) editable only before Active (Pending, Confirmed).
    - Notes can be updated in Active, but completed/cancelled bookings are read-only.
    - Snapshot rate is preserved if vehicle unchanged.
    - Returns updated document with oldTotalAmountPaise and newTotalAmountPaise.
    """
    now = clock_now if clock_now is not None else _now_utc()
    updated_doc: dict[str, Any] = {}

    def transaction_callback(session: Optional[ClientSession]) -> None:
        booking = db["bookings"].find_one(
            {"_id": booking_id, "tenantId": tenant_id, "deletedAt": None},
            session=session,
        )
        if not booking:
            raise BookingNotFoundError("Booking not found.")

        curr_status = booking["status"]
        if curr_status in [BookingStatus.completed.value, BookingStatus.cancelled.value, BookingStatus.no_show.value]:
            raise BookingStatusConflictError("Completed and cancelled bookings cannot be edited.")

        core_change = (
            customer_id is not None
            or vehicle_id is not None
            or start_date is not None
            or end_date is not None
            or pickup_location is not None
            or discount_paise is not None
        )

        if core_change and curr_status not in [BookingStatus.pending.value, BookingStatus.confirmed.value]:
            raise BookingStatusConflictError("Active bookings cannot modify rental dates, vehicle, customer, or pricing.")

        update_fields: dict[str, Any] = {"updatedAt": now}
        old_total = booking["totalAmountPaise"]

        target_vehicle_oid = booking["vehicleId"]
        target_customer_oid = booking["customerId"]
        target_start = start_date if start_date is not None else booking["startDate"]
        target_end = end_date if end_date is not None else booking["endDate"]
        daily_rate_paise = booking["dailyRatePaise"]  # Default to snapshot rate

        # Serialize on current vehicle guard
        apply_booking_guard(db, target_vehicle_oid, tenant_id, session=session)

        # 1. Customer change (validated in-tenant)
        if customer_id is not None and ObjectId(customer_id) != target_customer_oid:
            new_cust_oid = ObjectId(customer_id)
            new_cust = db["customers"].find_one(
                {"_id": new_cust_oid, "tenantId": tenant_id, "deletedAt": None},
                session=session,
            )
            if not new_cust:
                raise CustomerNotFoundError("Customer not found.")
            target_customer_oid = new_cust_oid
            update_fields["customerId"] = new_cust_oid
            update_fields["customerSnapshot"] = {
                "name": new_cust.get("name", ""),
                "phone": new_cust.get("phone", ""),
                "email": new_cust.get("email"),
            }

        # 2. Vehicle change (allowed only before Active)
        # TODO: Forbid vehicle change once payments exist in Phase 4.
        if vehicle_id is not None and ObjectId(vehicle_id) != target_vehicle_oid:
            new_veh_oid = ObjectId(vehicle_id)
            apply_booking_guard(db, new_veh_oid, tenant_id, session=session)
            new_veh = db["vehicles"].find_one(
                {"_id": new_veh_oid, "tenantId": tenant_id, "deletedAt": None},
                session=session,
            )
            if not new_veh:
                raise VehicleNotFoundError("Vehicle not found.")
            if new_veh.get("availability") == "Maintenance":
                raise VehicleUnderMaintenanceError("Vehicle is currently under maintenance.")

            daily_rate_raw = new_veh.get("dailyRate") or new_veh.get("price")
            if daily_rate_raw is None or daily_rate_raw <= 0:
                raise VehicleInvalidRateError("Vehicle has no valid daily rate.")
            daily_rate_paise = float_to_paise(daily_rate_raw)
            if daily_rate_paise <= 0:
                raise VehicleInvalidRateError("Vehicle has no valid daily rate.")

            target_vehicle_oid = new_veh_oid
            update_fields["vehicleId"] = new_veh_oid
            update_fields["dailyRatePaise"] = daily_rate_paise
            update_fields["securityDepositPaise"] = float_to_paise(new_veh.get("securityDeposit"))
            update_fields["vehicleSnapshot"] = {
                "name": new_veh.get("name", ""),
                "registration": new_veh.get("registration", ""),
                "registrationNumber": new_veh.get("registrationNumber") or new_veh.get("registration", "").replace(" ", "").upper(),
                "type": new_veh.get("type"),
            }

        # 3. Dates validation & overlap check
        if start_date is not None or end_date is not None or vehicle_id is not None:
            validate_booking_dates(
                start_date=target_start,
                end_date=target_end,
                now=now,
                grace_period_days=grace_period_days,
            )
            conflict = check_overlap(
                db=db,
                tenant_id=tenant_id,
                vehicle_id=target_vehicle_oid,
                start_date=target_start,
                end_date=target_end,
                exclude_booking_id=booking_id,
                session=session,
                now=now,
            )
            if conflict:
                raise OverlapConflictError("Vehicle is already booked for the selected rental period.")

            update_fields["startDate"] = target_start
            update_fields["endDate"] = target_end
            new_billable_days = calculate_billable_days(target_start, target_end)
            update_fields["billableDays"] = new_billable_days
        else:
            new_billable_days = booking["billableDays"]

        # 4. Pricing recalculation from snapshot rate (or new rate if vehicle changed)
        new_base_amount_paise = new_billable_days * daily_rate_paise
        update_fields["baseAmountPaise"] = new_base_amount_paise

        effective_discount = (
            discount_paise if discount_paise is not None else booking.get("discountPaise", 0)
        )
        if discount_paise is not None and discount_paise > 0 and user_role == "staff":
            raise BookingValidationError("Staff members cannot apply discounts.")

        if effective_discount > new_base_amount_paise:
            raise BookingValidationError("Discount cannot exceed base rental amount.")

        update_fields["discountPaise"] = effective_discount
        new_total_paise = new_base_amount_paise - effective_discount
        update_fields["totalAmountPaise"] = new_total_paise

        if pickup_location is not None:
            update_fields["pickupLocation"] = pickup_location
        if notes is not None:
            update_fields["notes"] = notes

        # CAS update: must still be in the expected pre-active status if core fields changed
        status_cas = (
            [BookingStatus.pending.value, BookingStatus.confirmed.value]
            if core_change
            else [BookingStatus.pending.value, BookingStatus.confirmed.value, BookingStatus.active.value]
        )
        res = db["bookings"].update_one(
            {
                "_id": booking_id,
                "tenantId": tenant_id,
                "status": {"$in": status_cas},
                "deletedAt": None,
            },
            {"$set": update_fields},
            session=session,
        )
        if res.matched_count == 0:
            latest = db["bookings"].find_one({"_id": booking_id, "tenantId": tenant_id, "deletedAt": None}, session=session)
            if not latest:
                raise BookingNotFoundError("Booking not found.")
            raise BookingStatusConflictError(f"Cannot edit booking in status '{latest['status']}'.")

        res_doc = db["bookings"].find_one({"_id": booking_id}, session=session)
        res_doc["oldTotalAmountPaise"] = old_total
        res_doc["newTotalAmountPaise"] = new_total_paise
        updated_doc.update(res_doc)

    execute_in_transaction(client, transaction_callback)
    return updated_doc


def soft_delete_booking(
    db: Any,
    tenant_id: ObjectId,
    booking_id: ObjectId,
    user_role: str,
) -> None:
    """
    Soft-delete booking with role and status invariants:
    - Allowed only for Pending and Cancelled bookings.
    - Owner and manager only (staff -> 403).
    - Confirmed or active -> 409.
    - Completed -> 409.
    """
    if user_role not in ["owner", "manager"]:
        raise BookingValidationError("Insufficient permissions to delete bookings.")

    booking = db["bookings"].find_one({"_id": booking_id, "tenantId": tenant_id, "deletedAt": None})
    if not booking:
        raise BookingNotFoundError("Booking not found.")

    curr_status = booking["status"]
    if curr_status in [BookingStatus.confirmed.value, BookingStatus.active.value]:
        raise BookingStatusConflictError("Cannot delete an active or confirmed booking. Cancel the booking first.")
    if curr_status == BookingStatus.completed.value:
        raise BookingStatusConflictError("Completed bookings cannot be deleted.")

    res = db["bookings"].update_one(
        {
            "_id": booking_id,
            "tenantId": tenant_id,
            "status": {"$in": [BookingStatus.pending.value, BookingStatus.cancelled.value]},
            "deletedAt": None,
        },
        {"$set": {"deletedAt": _now_utc(), "updatedAt": _now_utc()}},
    )
    if res.matched_count == 0:
        latest = db["bookings"].find_one({"_id": booking_id, "tenantId": tenant_id, "deletedAt": None})
        if not latest:
            raise BookingNotFoundError("Booking not found.")
        raise BookingStatusConflictError(f"Cannot delete booking in status '{latest['status']}'.")
