"""
Booking router for Phase 3a:
- Vehicle availability checking (GET /availability)
- Concurrency-guarded booking creation (POST /)
"""

from __future__ import annotations

import logging
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
from app.modules.bookings.schemas import BookingCreate
from app.modules.bookings.service import (
    MAX_BOOKING_DURATION_DAYS,
    BookingTransactionTimeoutError,
    BookingValidationError,
    CustomerNotFoundError,
    OverlapConflictError,
    VehicleInvalidRateError,
    VehicleNotFoundError,
    VehicleUnderMaintenanceError,
    check_overlap,
    create_booking_guarded,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
    return {
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
        "createdAt": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "updatedAt": updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
    }


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
# 2. Create booking (POST /)
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
