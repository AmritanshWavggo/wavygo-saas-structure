"""
Customer endpoints matching WavyGo platform and vehicles API conventions.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.core.responses import success
from app.db.mongodb import get_database
from app.modules.auth.deps import TenantContext, get_current_tenant, require_role
from app.modules.auth.models import UserRole
from app.modules.customers.models import CustomerStatus
from app.modules.customers.schemas import (
    CustomerCreate,
    CustomerMetricsResponse,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter()

_LIST_MAX_LIMIT = 100
_LIST_DEFAULT_LIMIT = 20


def _get_customers_col():
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not available.")
    return db["customers"]


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
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "phone": doc.get("phone", ""),
        "email": doc.get("email"),
        "status": doc.get("status", CustomerStatus.review.value),
        "notes": doc.get("notes"),
        "bookings": None,
        "active": None,
        "paid": None,
        "pending": None,
        "createdAt": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "updatedAt": updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
    }


# ---------------------------------------------------------------------------
# 1. List customers (GET /)
# ---------------------------------------------------------------------------
@router.get("")
@router.get("/")
def list_customers(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    search: Optional[str] = Query(default=None, max_length=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=_LIST_DEFAULT_LIMIT, ge=1, le=_LIST_MAX_LIMIT),
) -> dict:
    """
    List customers with optional search, status filtering, and pagination.
    Matches vehicles list conventions.
    """
    col = _get_customers_col()
    t_id = _tenant_id(tenant)
    query: dict[str, Any] = {"tenantId": t_id, "deletedAt": None}

    # Search filter: escape regex so characters like ".*" are treated as literals
    if search:
        raw_search = search.strip()
        if raw_search:
            escaped = re.escape(raw_search)
            or_clauses = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"email": {"$regex": escaped, "$options": "i"}},
            ]
            # Normalise phone searches to digits
            phone_digits = re.sub(r"\D", "", raw_search)
            if phone_digits:
                or_clauses.append({"phone": {"$regex": re.escape(phone_digits), "$options": "i"}})
            else:
                or_clauses.append({"phone": {"$regex": escaped, "$options": "i"}})
            query["$or"] = or_clauses

    # Status filter
    if status_filter:
        allowed = {s.value for s in CustomerStatus}
        if status_filter not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{status_filter}'. Allowed: {sorted(allowed)}.",
            )
        query["status"] = status_filter

    skip = (page - 1) * limit
    total = col.count_documents(query)
    cursor = col.find(query).sort("createdAt", -1).skip(skip).limit(limit)
    items = [_doc_to_response(doc) for doc in cursor]

    return success(items, meta={"total": total, "page": page, "limit": limit})


# ---------------------------------------------------------------------------
# 2. Customer metrics (GET /metrics)
# Declared BEFORE GET /{id} so that it is not shadowed by path param routing!
# ---------------------------------------------------------------------------
@router.get("/metrics")
def get_customer_metrics(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    """
    Get customer metrics scoped to current tenant.
    totalCollected and pendingDues return None until financial phases.
    """
    col = _get_customers_col()
    t_id = _tenant_id(tenant)
    base_filter = {"tenantId": t_id, "deletedAt": None}

    total_customers = col.count_documents(base_filter)
    verified_profiles = col.count_documents({**base_filter, "status": CustomerStatus.verified.value})

    return success({
        "totalCustomers": total_customers,
        "verifiedProfiles": verified_profiles,
        "totalCollected": None,
        "pendingDues": None,
    })


# ---------------------------------------------------------------------------
# 3. Get single customer (GET /{id})
# ---------------------------------------------------------------------------
@router.get("/{id}")
def get_customer(
    id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    col = _get_customers_col()
    t_id = _tenant_id(tenant)
    doc = col.find_one({"_id": ObjectId(id), "tenantId": t_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    return success(_doc_to_response(doc))


# ---------------------------------------------------------------------------
# 4. Create customer (POST /)
# ---------------------------------------------------------------------------
@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    col = _get_customers_col()
    t_id = _tenant_id(tenant)
    u_id = _user_id(tenant)
    role = _user_role(tenant)

    # Status rules: staff-created customers are always "Review". Only owner/manager may set status.
    if role == UserRole.staff.value:
        if payload.status is not None and payload.status != CustomerStatus.review:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff members cannot set customer status to Verified.",
            )
        effective_status = CustomerStatus.review.value
    else:
        effective_status = (payload.status or CustomerStatus.review).value

    # Duplicate phone check in same tenant
    existing = col.find_one({"tenantId": t_id, "phone": payload.phone, "deletedAt": None})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number already exists in your fleet.",
        )

    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "name": payload.name,
        "phone": payload.phone,
        "email": payload.email,
        "status": effective_status,
        "notes": payload.notes,
        "tenantId": t_id,
        "createdBy": u_id,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
    }

    try:
        result = col.insert_one(doc)
        doc["_id"] = result.inserted_id
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number already exists in your fleet.",
        ) from exc

    return success(_doc_to_response(doc), status_code=201)


# ---------------------------------------------------------------------------
# 5. Update customer (PATCH /{id})
# ---------------------------------------------------------------------------
@router.patch("/{id}")
def update_customer(
    id: str,
    payload: CustomerUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    col = _get_customers_col()
    t_id = _tenant_id(tenant)
    customer_id = ObjectId(id)
    role = _user_role(tenant)

    existing = col.find_one({"_id": customer_id, "tenantId": t_id, "deletedAt": None})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    update_dict = payload.model_dump(exclude_unset=True)

    # Status permissions: only owner/manager may change status.
    if "status" in update_dict and role == UserRole.staff.value:
        status_val = update_dict["status"]
        status_str = status_val.value if hasattr(status_val, "value") else str(status_val)
        if status_str != existing.get("status"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff members cannot modify customer status.",
            )

    # If updating phone, verify uniqueness in tenant
    new_phone = update_dict.get("phone")
    if new_phone and new_phone != existing.get("phone"):
        dup = col.find_one({"tenantId": t_id, "phone": new_phone, "deletedAt": None, "_id": {"$ne": customer_id}})
        if dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this phone number already exists in your fleet.",
            )

    if not update_dict:
        return success(_doc_to_response(existing))

    # Convert status enum to string if present
    if "status" in update_dict and update_dict["status"] is not None:
        val = update_dict["status"]
        update_dict["status"] = val.value if hasattr(val, "value") else str(val)

    update_dict["updatedAt"] = datetime.now(timezone.utc)

    try:
        col.update_one({"_id": customer_id, "tenantId": t_id}, {"$set": update_dict})
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number already exists in your fleet.",
        ) from exc

    updated_doc = col.find_one({"_id": customer_id, "tenantId": t_id})
    return success(_doc_to_response(updated_doc))


# ---------------------------------------------------------------------------
# 6. Delete customer (DELETE /{id}) - Owner & Manager only
# ---------------------------------------------------------------------------
@router.delete("/{id}")
def delete_customer(
    id: str,
    tenant: Annotated[TenantContext, Depends(require_role(UserRole.owner, UserRole.manager))],
) -> dict:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    col = _get_customers_col()
    t_id = _tenant_id(tenant)
    customer_id = ObjectId(id)

    existing = col.find_one({"_id": customer_id, "tenantId": t_id, "deletedAt": None})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    db = col.database
    blocking_booking = db["bookings"].find_one({
        "tenantId": t_id,
        "customerId": customer_id,
        "deletedAt": None,
        "status": {"$in": ["Pending", "Confirmed", "Active"]},
    })
    if blocking_booking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete customer with active or upcoming bookings. Cancel or complete all bookings first.",
        )

    now = datetime.now(timezone.utc)
    col.update_one({"_id": customer_id, "tenantId": t_id}, {"$set": {"deletedAt": now, "updatedAt": now}})

    return success({"id": str(customer_id), "deleted": True})
