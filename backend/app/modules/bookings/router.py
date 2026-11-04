"""
Booking router for Phase 3:
- Vehicle availability checking (GET /availability)
- Concurrency-guarded booking creation (POST /)
- Server-side paginated list with search, filter, and sort (GET /)
- Single booking retrieval (GET /{id})
- Guarded booking update with snapshot rate recalculation (PATCH /{id})
- Compare-and-set status transition with role enforcement (PATCH /{id}/status)
- Soft delete with role and status invariants (DELETE /{id})
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.responses import success
from app.db.mongodb import get_database
from app.modules.auth.deps import TenantContext, get_current_tenant
from app.modules.auth.models import UserRole
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.schemas import (
    BookingCreate,
    BookingStatusTransition,
    BookingUpdate,
)
from app.modules.bookings.service import (
    MAX_BOOKING_DURATION_DAYS,
    BookingNotFoundError,
    BookingStatusConflictError,
    BookingTransactionTimeoutError,
    BookingValidationError,
    CustomerNotFoundError,
    OverlapConflictError,
    VehicleInvalidRateError,
    VehicleNotFoundError,
    VehicleUnderMaintenanceError,
    check_overlap,
    create_booking_guarded,
    soft_delete_booking,
    transition_booking_status,
    update_booking_guarded,
)

logger = logging.getLogger(__name__)

router = APIRouter()

SORT_WHITELIST = {
    "createdAt": "createdAt",
    "startDate": "startDate",
    "endDate": "endDate",
    "totalAmountPaise": "totalAmountPaise",
    "bookingNumber": "bookingNumber",
    "status": "status",
}


def _get_db():
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please retry.",
        )
    return db


def _tenant_id(context: TenantContext) -> ObjectId:
    val = context.get("tenantId") or context.get("tenant_id")
    if isinstance(val, ObjectId):
        return val
    return ObjectId(str(val))


def _user_id(context: TenantContext) -> ObjectId:
    val = context.get("_id") or context.get("user_id")
    if isinstance(val, ObjectId):
        return val
    return ObjectId(str(val))


def _user_role(context: TenantContext) -> str:
    role_val = context.get("role")
    if hasattr(role_val, "value"):
        return role_val.value
    return str(role_val)


def _doc_to_response(doc: dict) -> dict:
    created_at = doc.get("createdAt")
    updated_at = doc.get("updatedAt")
    start_date = doc.get("startDate")
    end_date = doc.get("endDate")
    confirmed_at = doc.get("confirmedAt")
    activated_at = doc.get("activatedAt")
    completed_at = doc.get("completedAt")
    cancelled_at = doc.get("cancelledAt")

    resp = {
        "id": str(doc["_id"]),
        "bookingNumber": doc.get("bookingNumber"),
        "customerId": str(doc.get("customerId")),
        "vehicleId": str(doc.get("vehicleId")),
        "startDate": start_date.isoformat() if isinstance(start_date, datetime) else start_date,
        "endDate": end_date.isoformat() if isinstance(end_date, datetime) else end_date,
        "pickupLocation": doc.get("pickupLocation"),
        "status": doc.get("status"),
        "currency": doc.get("currency", "INR"),
        "dailyRatePaise": doc.get("dailyRatePaise"),
        "billableDays": doc.get("billableDays"),
        "baseAmountPaise": doc.get("baseAmountPaise"),
        "discountPaise": doc.get("discountPaise", 0),
        "securityDepositPaise": doc.get("securityDepositPaise", 0),
        "totalAmountPaise": doc.get("totalAmountPaise"),
        "vehicleSnapshot": doc.get("vehicleSnapshot"),
        "customerSnapshot": doc.get("customerSnapshot"),
        "notes": doc.get("notes"),
        "cancelReason": doc.get("cancelReason"),
        "confirmedAt": confirmed_at.isoformat() if isinstance(confirmed_at, datetime) else confirmed_at,
        "activatedAt": activated_at.isoformat() if isinstance(activated_at, datetime) else activated_at,
        "completedAt": completed_at.isoformat() if isinstance(completed_at, datetime) else completed_at,
        "cancelledAt": cancelled_at.isoformat() if isinstance(cancelled_at, datetime) else cancelled_at,
        "createdAt": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "updatedAt": updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
    }
    if "oldTotalAmountPaise" in doc:
        resp["oldTotalAmountPaise"] = doc["oldTotalAmountPaise"]
    if "newTotalAmountPaise" in doc:
        resp["newTotalAmountPaise"] = doc["newTotalAmountPaise"]
    return resp


# ---------------------------------------------------------------------------
# 1. Check vehicle availability (GET /availability)
# ---------------------------------------------------------------------------
@router.get("/availability")
def check_vehicle_availability(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    vehicle_id: str = Query(..., alias="vehicleId"),
    start_date: datetime = Query(..., alias="startDate"),
    end_date: datetime = Query(..., alias="endDate"),
    exclude_booking_id: Optional[str] = Query(default=None, alias="excludeBookingId"),
) -> dict:
    """
    Check if a vehicle is available for a specified rental interval [startDate, endDate).
    """
    if start_date.tzinfo is None or start_date.tzinfo.utcoffset(start_date) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="startDate must include a timezone offset.",
        )
    if end_date.tzinfo is None or end_date.tzinfo.utcoffset(end_date) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="endDate must include a timezone offset.",
        )
    utc_start = start_date.astimezone(timezone.utc)
    utc_end = end_date.astimezone(timezone.utc)

    if utc_end <= utc_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End date must be strictly after start date.",
        )

    if (utc_end - utc_start).total_seconds() > MAX_BOOKING_DURATION_DAYS * 86400:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rental duration cannot exceed 90 days.",
        )

    if not ObjectId.is_valid(vehicle_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vehicleId format.",
        )
    vehicle_oid = ObjectId(vehicle_id)

    exclude_oid: Optional[ObjectId] = None
    if exclude_booking_id:
        if not ObjectId.is_valid(exclude_booking_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid excludeBookingId format.",
            )
        exclude_oid = ObjectId(exclude_booking_id)

    db = _get_db()
    t_id = _tenant_id(tenant)

    vehicle = db["vehicles"].find_one({"_id": vehicle_oid, "tenantId": t_id, "deletedAt": None})
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found.",
        )

    conflict = check_overlap(
        db=db,
        tenant_id=t_id,
        vehicle_id=vehicle_oid,
        start_date=utc_start,
        end_date=utc_end,
        exclude_booking_id=exclude_oid,
    )

    if conflict:
        c_start = conflict.get("startDate")
        c_end = conflict.get("endDate")
        conflicts_list = [
            {
                "bookingNumber": conflict.get("bookingNumber"),
                "startDate": c_start.isoformat() if isinstance(c_start, datetime) else c_start,
                "endDate": c_end.isoformat() if isinstance(c_end, datetime) else c_end,
                "status": conflict.get("status"),
            }
        ]
        return success({"available": False, "conflicts": conflicts_list})

    return success({"available": True, "conflicts": []})


# ---------------------------------------------------------------------------
# 2. List bookings with pagination, search, filters, sort (GET /)
# ---------------------------------------------------------------------------
@router.get("")
@router.get("/")
def list_bookings(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    vehicle_id: Optional[str] = Query(default=None, alias="vehicleId"),
    customer_id: Optional[str] = Query(default=None, alias="customerId"),
    start_date_from: Optional[datetime] = Query(default=None, alias="startDateFrom"),
    start_date_to: Optional[datetime] = Query(default=None, alias="startDateTo"),
    search: Optional[str] = Query(default=None, max_length=100),
    sort_by: str = Query(default="createdAt", alias="sortBy"),
    sort_order: str = Query(default="desc", alias="sortOrder", pattern="^(asc|desc)$"),
) -> dict:
    """
    List bookings scoped to current tenant with server-side pagination, search, and filters.
    """
    if sort_by not in SORT_WHITELIST:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sortBy field '{sort_by}'. Allowed: {sorted(SORT_WHITELIST.keys())}.",
        )

    t_id = _tenant_id(tenant)
    db = _get_db()
    query: dict[str, Any] = {"tenantId": t_id, "deletedAt": None}

    if status_filter:
        valid_statuses = {s.value for s in BookingStatus}
        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{status_filter}'. Allowed: {sorted(valid_statuses)}.",
            )
        query["status"] = status_filter

    if vehicle_id:
        if not ObjectId.is_valid(vehicle_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid vehicleId format.",
            )
        query["vehicleId"] = ObjectId(vehicle_id)

    if customer_id:
        if not ObjectId.is_valid(customer_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid customerId format.",
            )
        query["customerId"] = ObjectId(customer_id)

    if start_date_from or start_date_to:
        date_filter = {}
        if start_date_from:
            date_filter["$gte"] = start_date_from.astimezone(timezone.utc)
        if start_date_to:
            date_filter["$lte"] = start_date_to.astimezone(timezone.utc)
        query["startDate"] = date_filter

    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"bookingNumber": {"$regex": escaped, "$options": "i"}},
            {"customerSnapshot.name": {"$regex": escaped, "$options": "i"}},
            {"customerSnapshot.phone": {"$regex": escaped, "$options": "i"}},
            {"vehicleSnapshot.name": {"$regex": escaped, "$options": "i"}},
            {"vehicleSnapshot.registration": {"$regex": escaped, "$options": "i"}},
            {"vehicleSnapshot.registrationNumber": {"$regex": escaped, "$options": "i"}},
        ]

    sort_field = SORT_WHITELIST[sort_by]
    sort_dir = 1 if sort_order == "asc" else -1
    sort_spec = [(sort_field, sort_dir), ("_id", sort_dir)]

    col = db["bookings"]
    total = col.count_documents(query)
    skip = (page - 1) * limit
    cursor = col.find(query).sort(sort_spec).skip(skip).limit(limit)
    items = [_doc_to_response(doc) for doc in cursor]

    return success(items, meta={"total": total, "page": page, "limit": limit})


# ---------------------------------------------------------------------------
# 3. Create booking (POST /)
# ---------------------------------------------------------------------------
@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Create a new booking using the concurrency-guarded transaction engine.
    Eliminates write-skew via serialization point on the vehicle document.
    """
    role = _user_role(tenant)
    if role == UserRole.staff.value and payload.discount_paise > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members cannot apply discounts.",
        )

    t_id = _tenant_id(tenant)
    u_id = _user_id(tenant)
    db = _get_db()
    client = db.client

    try:
        doc = create_booking_guarded(
            client=client,
            db=db,
            tenant_id=t_id,
            user_id=u_id,
            vehicle_oid=ObjectId(payload.vehicle_id),
            customer_oid=ObjectId(payload.customer_id),
            start_date=payload.start_date,
            end_date=payload.end_date,
            pickup_location=payload.pickup_location,
            status=payload.status or BookingStatus.confirmed,
            discount_paise=payload.discount_paise,
            notes=payload.notes,
            grace_period_days=settings.booking_grace_period_days,
        )
    except VehicleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (OverlapConflictError, VehicleUnderMaintenanceError, VehicleInvalidRateError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except BookingTransactionTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please retry.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error creating booking: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return success(_doc_to_response(doc), status_code=201)


# ---------------------------------------------------------------------------
# 4. Get single booking (GET /{id})
# ---------------------------------------------------------------------------
@router.get("/{id}")
def get_booking(
    id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Get booking by ID scoped strictly to caller's tenant.
    Cross-tenant IDs return 404 with zero information leakage.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    t_id = _tenant_id(tenant)
    db = _get_db()
    doc = db["bookings"].find_one({"_id": ObjectId(id), "tenantId": t_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    return success(_doc_to_response(doc))


# ---------------------------------------------------------------------------
# 5. Update booking (PATCH /{id})
# ---------------------------------------------------------------------------
@router.patch("/{id}")
def update_booking(
    id: str,
    payload: BookingUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Guarded edit of booking with recalculation from snapshot rate:
    - Core fields editable only before Active.
    - Recalculates total and returns oldTotalAmountPaise and newTotalAmountPaise.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    booking_oid = ObjectId(id)
    t_id = _tenant_id(tenant)
    role = _user_role(tenant)
    db = _get_db()
    client = db.client

    try:
        updated_doc = update_booking_guarded(
            client=client,
            db=db,
            tenant_id=t_id,
            booking_id=booking_oid,
            user_role=role,
            customer_id=payload.customer_id,
            vehicle_id=payload.vehicle_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            pickup_location=payload.pickup_location,
            discount_paise=payload.discount_paise,
            notes=payload.notes,
            grace_period_days=settings.booking_grace_period_days,
        )
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (VehicleNotFoundError, CustomerNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (BookingStatusConflictError, OverlapConflictError, VehicleUnderMaintenanceError, VehicleInvalidRateError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BookingValidationError as exc:
        if "Staff members cannot" in str(exc):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except BookingTransactionTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please retry.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error updating booking: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return success(_doc_to_response(updated_doc))


# ---------------------------------------------------------------------------
# 6. Status transition (PATCH /{id}/status)
# ---------------------------------------------------------------------------
@router.patch("/{id}/status")
def transition_status(
    id: str,
    payload: BookingStatusTransition,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Compare-and-set status transition with role-based permission checks:
    - Confirmed -> Cancelled requires owner or manager.
    - Confirmed -> Active is refused if vehicle already has an active booking.
    - Sets respective timestamp (confirmedAt, activatedAt, completedAt, cancelledAt).
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    booking_oid = ObjectId(id)
    t_id = _tenant_id(tenant)
    role = _user_role(tenant)
    db = _get_db()

    try:
        updated = transition_booking_status(
            db=db,
            tenant_id=t_id,
            booking_id=booking_oid,
            target_status=payload.status,
            user_role=role,
            cancel_reason=payload.cancel_reason,
        )
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (BookingStatusConflictError, OverlapConflictError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BookingValidationError as exc:
        if "Staff members cannot" in str(exc):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error transitioning booking status: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return success(_doc_to_response(updated))


# ---------------------------------------------------------------------------
# 7. Soft delete booking (DELETE /{id})
# ---------------------------------------------------------------------------
@router.delete("/{id}")
def delete_booking(
    id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Soft-delete booking:
    - Permitted only for Pending and Cancelled bookings.
    - Owner and manager only (staff -> 403).
    - Confirmed, active, or completed -> 409.
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    booking_oid = ObjectId(id)
    t_id = _tenant_id(tenant)
    role = _user_role(tenant)
    db = _get_db()

    try:
        soft_delete_booking(
            db=db,
            tenant_id=t_id,
            booking_id=booking_oid,
            user_role=role,
        )
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BookingStatusConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error deleting booking: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return success({"deleted": True, "id": id})
