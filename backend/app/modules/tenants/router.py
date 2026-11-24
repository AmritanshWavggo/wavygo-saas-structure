from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.db.mongodb import get_database
from app.modules.auth.security import get_current_vendor, get_vendors_collection
from app.modules.tenants.schemas import (
    RentalRulesSchema,
    TenantNotificationSettings,
    TenantPermissions,
    TenantResponse,
    TenantStatusUpdate,
    TenantUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db():
    return get_database()


def _serialize_tenant(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert raw Mongo vendor/tenant document to a TenantResponse-compatible dict."""
    item = dict(doc)
    item["id"] = str(item.pop("_id", item.get("id", "")))
    item.pop("password_hash", None)
    item.pop("email_normalized", None)

    # Standardize field names
    item["businessName"] = item.get("business_name") or item.get("businessName") or ""
    item["ownerName"] = item.get("owner_name") or item.get("ownerName") or item.get("owner") or ""
    item["email"] = item.get("email") or ""
    item["phone"] = item.get("phone") or ""
    item["address"] = item.get("address") or ""
    item["city"] = item.get("city") or ""
    item["state"] = item.get("state") or ""
    item["pincode"] = item.get("pincode") or ""
    item["gstin"] = item.get("gstin") or ""
    item["status"] = "Active" if item.get("is_active", True) else item.get("status", "Inactive")
    item["plan"] = item.get("plan") or "Growth"

    # Embedded objects with safe defaults
    rules = item.get("rental_rules") or item.get("rentalRules") or {}
    item["rentalRules"] = {
        "minimumRentalHours": rules.get("minimumRentalHours") or rules.get("minimum_rental_hours") or 24,
        "advanceBookingDays": rules.get("advanceBookingDays") or rules.get("advance_booking_days") or 90,
        "defaultSecurityDeposit": float(rules.get("defaultSecurityDeposit") or rules.get("default_security_deposit") or 2000.0),
        "cancellationHours": rules.get("cancellationHours") or rules.get("cancellation_hours") or 24,
        "currency": rules.get("currency") or "INR",
    }

    notifs = item.get("notifications") or {}
    item["notifications"] = {
        "bookingNotifications": notifs.get("bookingNotifications", notifs.get("booking_notifications", True)),
        "paymentNotifications": notifs.get("paymentNotifications", notifs.get("payment_notifications", True)),
        "maintenanceNotifications": notifs.get("maintenanceNotifications", notifs.get("maintenance_notifications", True)),
    }

    perms = item.get("permissions") or {}
    item["permissions"] = {
        "staffAccessLevel": perms.get("staffAccessLevel") or perms.get("staff_access_level") or "Bookings and customers",
        "invitePolicy": perms.get("invitePolicy") or perms.get("invite_policy") or "Owner approval",
    }

    created = item.get("created_at") or item.get("createdAt")
    item["createdAt"] = created.isoformat() if isinstance(created, datetime) else str(created or "")

    updated = item.get("updated_at") or item.get("updatedAt")
    item["updatedAt"] = updated.isoformat() if isinstance(updated, datetime) else str(updated or "")

    return item


@router.get("/current", response_model=TenantResponse, summary="Get current vendor tenant profile")
@router.get("/me", response_model=TenantResponse, summary="Get current vendor tenant profile (alias)")
def get_current_tenant_profile(
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
) -> dict[str, Any]:
    """Retrieve the business profile, rental rules, and workspace configuration for the authenticated vendor."""
    return _serialize_tenant(vendor)


@router.put("/current", response_model=TenantResponse, summary="Update current vendor tenant profile")
@router.put("/me", response_model=TenantResponse, summary="Update current vendor tenant profile (alias)")
@router.patch("/current", response_model=TenantResponse, summary="Patch current vendor tenant profile")
def update_current_tenant_profile(
    changes: TenantUpdate,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    vendors_col: Annotated[Collection[dict[str, Any]], Depends(get_vendors_collection)],
) -> dict[str, Any]:
    """Update business details, address, rental rules, notifications, or workspace permissions."""
    update_data = changes.model_dump(by_alias=True, exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes provided.")

    now = datetime.now(timezone.utc)
    set_fields: dict[str, Any] = {"updated_at": now}

    for key, value in update_data.items():
        if key == "businessName":
            set_fields["business_name"] = value
        elif key == "ownerName":
            set_fields["owner_name"] = value
        elif key == "rentalRules":
            set_fields["rental_rules"] = value
        else:
            set_fields[key] = value

    try:
        vendors_col.update_one({"_id": vendor["_id"]}, {"$set": set_fields})
        updated = vendors_col.find_one({"_id": vendor["_id"]})
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
        return _serialize_tenant(updated)
    except PyMongoError as exc:
        logger.exception("Failed to update tenant profile: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save tenant changes.")


@router.get("/stats", summary="Get aggregated tenant fleet, rental, and staff metrics")
def get_tenant_stats(
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
) -> dict[str, Any]:
    """Calculate and return real-time operational statistics for the tenant."""
    db = _get_db()
    tenant_oid = vendor["_id"]
    tenant_str = str(tenant_oid)

    total_vehicles = 0
    available_vehicles = 0
    rented_vehicles = 0
    maintenance_vehicles = 0
    total_customers = 0
    active_bookings = 0
    total_staff = 0
    total_revenue = 0.0

    if db is not None:
        try:
            # Vehicles query
            veh_query = {"$or": [{"tenant_id": tenant_str}, {"tenant_id": tenant_oid}, {"tenant_id": None}, {"tenant_id": {"$exists": False}}]}
            vehicles = list(db["vehicles"].find(veh_query, {"fleetAvailability": 1, "availability": 1, "dailyRate": 1, "price": 1}))
            total_vehicles = len(vehicles)
            for v in vehicles:
                avail = v.get("fleetAvailability") or v.get("availability") or "Available"
                if avail == "Available":
                    available_vehicles += 1
                elif avail == "Rented":
                    rented_vehicles += 1
                elif avail == "Maintenance":
                    maintenance_vehicles += 1

            # Customers
            cust_query = {"$or": [{"tenant_id": tenant_str}, {"tenant_id": tenant_oid}, {"tenant_id": None}, {"tenant_id": {"$exists": False}}]}
            total_customers = db["customers"].count_documents(cust_query)

            # Bookings
            book_query = {"$or": [{"tenant_id": tenant_str}, {"tenant_id": tenant_oid}, {"tenant_id": None}, {"tenant_id": {"$exists": False}}]}
            bookings = list(db["bookings"].find(book_query, {"status": 1, "total_amount": 1, "paid": 1}))
            for b in bookings:
                if b.get("status") in ["Active", "Confirmed", "In Progress"]:
                    active_bookings += 1
                total_revenue += float(b.get("paid") or b.get("total_amount") or 0.0)

            # Staff
            staff_query = {"$or": [{"tenant_id": tenant_str}, {"tenant_id": tenant_oid}]}
            total_staff = db["staff_members"].count_documents(staff_query)

        except Exception as exc:
            logger.warning("Error computing tenant stats: %s", exc)

    return {
        "tenant_id": tenant_str,
        "business_name": vendor.get("business_name") or vendor.get("businessName") or "",
        "vehicles": {
            "total": total_vehicles,
            "available": available_vehicles,
            "rented": rented_vehicles,
            "maintenance": maintenance_vehicles,
        },
        "customers": total_customers,
        "active_bookings": active_bookings,
        "staff_members": total_staff,
        "total_revenue": round(total_revenue, 2),
    }


@router.get("", response_model=List[TenantResponse], summary="List all tenants")
def list_tenants(
    search: Optional[str] = Query(default=None, max_length=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Any = Depends(_get_db),
) -> List[dict[str, Any]]:
    """List tenants with optional search and status filtering (system/admin view)."""
    if db is None:
        return []

    query: dict[str, Any] = {}
    if status_filter:
        if status_filter.lower() == "active":
            query["is_active"] = True
        elif status_filter.lower() == "inactive":
            query["is_active"] = False

    if search:
        query["$or"] = [
            {"business_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]

    try:
        cursor = db["vendors"].find(query).skip(skip).limit(limit)
        return [_serialize_tenant(doc) for doc in cursor]
    except PyMongoError as exc:
        logger.exception("Failed to query tenants: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to retrieve tenants.")


@router.get("/{tenant_id}", response_model=TenantResponse, summary="Get tenant by ID")
def get_tenant_by_id(
    tenant_id: str,
    vendors_col: Annotated[Collection[dict[str, Any]], Depends(get_vendors_collection)],
) -> dict[str, Any]:
    """Retrieve tenant details by MongoDB ObjectId or string id."""
    if not ObjectId.is_valid(tenant_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant ID format.")

    doc = vendors_col.find_one({"_id": ObjectId(tenant_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{tenant_id}' not found.")

    return _serialize_tenant(doc)


@router.patch("/{tenant_id}/status", response_model=TenantResponse, summary="Update tenant active status")
def update_tenant_status(
    tenant_id: str,
    payload: TenantStatusUpdate,
    vendors_col: Annotated[Collection[dict[str, Any]], Depends(get_vendors_collection)],
) -> dict[str, Any]:
    """Update tenant status (Active, Inactive, Suspended)."""
    if not ObjectId.is_valid(tenant_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant ID format.")

    is_active = payload.status in ["Active", "Trial"]
    now = datetime.now(timezone.utc)
    result = vendors_col.update_one(
        {"_id": ObjectId(tenant_id)},
        {"$set": {"is_active": is_active, "status": payload.status, "updated_at": now}},
    )

    if not result.matched_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{tenant_id}' not found.")

    updated = vendors_col.find_one({"_id": ObjectId(tenant_id)})
    return _serialize_tenant(updated)
