"""
Core domain logic, transaction runner, and concurrency controls for Bookings.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def validate_booking_dates(
    start_date: datetime,
    end_date: datetime,
    grace_period_days: int = 1,
    now: Optional[datetime] = None,
) -> None:
    """
    Validate rental interval bounds and constraints:
    - End date must be strictly after start date.
    - Duration cannot exceed 90 days.
    - Start date cannot be before the configured grace period.
    """
    if end_date <= start_date:
        raise BookingValidationError("End date must be strictly after start date.")

    duration_seconds = (end_date - start_date).total_seconds()
    if duration_seconds > MAX_BOOKING_DURATION_DAYS * 86400:
        raise BookingValidationError("Rental duration cannot exceed 90 days.")

    if now is None:
        now = datetime.now(timezone.utc)

    grace_boundary = now - timedelta(days=grace_period_days)
    if start_date < grace_boundary:
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
) -> Optional[dict]:
    """
    Query for overlapping bookings occupying the vehicle interval [start, end).
    Two intervals [A_start, A_end) and [B_start, B_end) overlap iff:
        A_start < B_end and A_end > B_start
    """
    effective_start = start_date - timedelta(minutes=buffer_minutes)
    effective_end = end_date + timedelta(minutes=buffer_minutes)

    query = {
        "tenantId": tenant_id,
        "vehicleId": vehicle_id,
        "status": {"$in": list(BLOCKING_STATUSES)},
        "deletedAt": None,
        "startDate": {"$lt": effective_end},
        "endDate": {"$gt": effective_start},
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
    validate_booking_dates(start_date, end_date, grace_period_days=grace_period_days, now=clock_now)
    booking_number = generate_booking_number(db, tenant_id, year=start_date.year)
    billable_days = calculate_billable_days(start_date, end_date)

    now = clock_now if clock_now is not None else datetime.now(timezone.utc)
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
