import logging
import re
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, NoReturn

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.modules.auth.security import get_current_vendor

logger = logging.getLogger(__name__)

CustomerStatus = Literal["Review", "Verified"]
router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=25)
    email: str | None = Field(default=None, max_length=254)
    status: CustomerStatus = "Review"
    email_verified: bool = False
    phone_verified: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"\+?[0-9][0-9\s().-]{5,23}", value):
            raise ValueError("Enter a valid phone number.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=7, max_length=25)
    email: str | None = Field(default=None, max_length=254)
    status: CustomerStatus | None = None

    @field_validator("name", "phone", "status", mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not re.fullmatch(r"\+?[0-9][0-9\s().-]{5,23}", value):
            raise ValueError("Enter a valid phone number.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "CustomerUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        return self


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    phone: str
    email: str | None = None
    status: CustomerStatus = "Review"
    email_verified: bool = False
    phone_verified: bool = False
    bookings: int = 0
    active: int = 0
    paid: float = 0
    pending: float = 0
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    skip: int
    limit: int


def get_customers_collection(request: Request) -> Collection[dict[str, Any]]:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not configured.",
        )

    return database["customers"]


def parse_customer_id(customer_id: str) -> ObjectId:
    if not ObjectId.is_valid(customer_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID.",
        )
    return ObjectId(customer_id)


class CustomerSendOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=3, max_length=254)
    channel: Literal["email", "phone"]
    customer_name: str | None = None


class CustomerVerifyOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=3, max_length=254)
    channel: Literal["email", "phone"]
    otp: str = Field(min_length=4, max_length=8)


def serialize_customer(document: dict[str, Any]) -> dict[str, Any]:
    customer = dict(document)
    customer["id"] = str(customer.pop("_id"))
    customer["email_verified"] = bool(customer.get("email_verified", customer.get("status") == "Verified"))
    customer["phone_verified"] = bool(customer.get("phone_verified", customer.get("status") == "Verified"))
    return customer


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def raise_storage_error() -> NoReturn:
    logger.exception("Customer database operation failed.")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Customer storage is unavailable.",
    )


@router.post("/send-otp")
def send_customer_otp(
    payload: CustomerSendOtpRequest,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
) -> dict[str, Any]:
    """Generate and dispatch a verification OTP to customer email or phone."""
    from app.services.otp_service import generate_otp, store_customer_otp

    otp = generate_otp(6)
    store_customer_otp(payload.target, payload.channel, otp, ttl_seconds=600)

    if payload.channel == "email":
        norm_email = payload.target.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", norm_email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid email address.")
        from app.services.email_service import send_customer_verification_email

        sent = send_customer_verification_email(norm_email, otp, payload.customer_name)
        if not sent:
            logger.warning("Customer verification email failed for %s", norm_email)
    else:
        norm_phone = normalize_phone(payload.target)
        if len(norm_phone) < 10:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid 10-digit mobile number.")
        from app.services.sms_service import send_sms_otp

        sent = send_sms_otp(norm_phone, otp, payload.customer_name)
        if not sent:
            logger.warning("Customer verification SMS failed for %s", norm_phone)

    return {
        "success": True,
        "channel": payload.channel,
        "message": f"Verification code sent to {payload.channel}.",
    }


@router.post("/verify-otp")
def verify_customer_otp_endpoint(
    payload: CustomerVerifyOtpRequest,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
) -> dict[str, Any]:
    """Verify submitted OTP code against Upstash Redis."""
    from app.services.otp_service import verify_customer_otp

    is_valid = verify_customer_otp(payload.target, payload.channel, payload.otp)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )
    return {
        "success": True,
        "verified": True,
        "channel": payload.channel,
        "message": f"{payload.channel.capitalize()} verified successfully.",
    }


@router.post("/{customer_id}/verify", response_model=CustomerResponse)
def verify_existing_customer(
    customer_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection[dict[str, Any]], Depends(get_customers_collection)],
) -> dict[str, Any]:
    """Manually or confirmedly mark a customer as Verified."""
    object_id = parse_customer_id(customer_id)
    now = datetime.now(timezone.utc)
    scoped_filter = {"_id": object_id, "tenant_id": vendor["_id"]}
    res = collection.update_one(
        scoped_filter,
        {
            "$set": {
                "status": "Verified",
                "phone_verified": True,
                "email_verified": True,
                "updated_at": now,
            }
        },
    )
    if not res.matched_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    doc = collection.find_one(scoped_filter)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return serialize_customer(doc)


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer: CustomerCreate,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection[dict[str, Any]], Depends(get_customers_collection)],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    # Determine verified status based on phone/email verification or explicit flag
    computed_status = customer.status
    if customer.phone_verified and (customer.email_verified or not customer.email):
        computed_status = "Verified"

    document: dict[str, Any] = {
        **customer.model_dump(exclude_none=True),
        "status": computed_status,
        "phone_verified": customer.phone_verified,
        "email_verified": customer.email_verified,
        "tenant_id": vendor["_id"],
        "phone_normalized": normalize_phone(customer.phone),
        "bookings": 0,
        "active": 0,
        "paid": 0,
        "pending": 0,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = collection.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number or email already exists.",
        ) from exc
    except PyMongoError:
        raise_storage_error()
    document["_id"] = result.inserted_id
    return serialize_customer(document)


@router.get("/", response_model=CustomerListResponse)
def list_customers(
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection[dict[str, Any]], Depends(get_customers_collection)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    status_filter: Annotated[CustomerStatus | None, Query(alias="status")] = None,
) -> dict[str, Any]:
    try:
        # If running with real MongoDB, ensure customers from bookings are backfilled
        database = getattr(collection, "database", None)
        if database is not None and hasattr(database, "__getitem__"):
            try:
                v_id = vendor["_id"]
                b_cursor = database["bookings"].find(
                    {"$or": [{"tenant_id": str(v_id)}, {"tenant_id": v_id}, {"vendor_id": str(v_id)}, {"vendor_id": v_id}]}
                )
                for b in b_cursor:
                    c_name = b.get("customer")
                    c_det = b.get("customer_details") or {}
                    c_phone = str(c_det.get("phone") or b.get("phone") or "").strip()
                    c_norm = normalize_phone(c_phone) if c_phone else ""
                    c_email = (c_det.get("email") or b.get("email") or "").strip().lower() or None
                    if c_name:
                        q: dict[str, Any] = {"tenant_id": v_id}
                        or_conds = []
                        if c_norm:
                            or_conds.append({"phone_normalized": c_norm})
                        if c_phone:
                            or_conds.append({"phone": c_phone})
                        if c_email:
                            or_conds.append({"email": c_email})
                        if or_conds:
                            q["$or"] = or_conds
                        else:
                            q["name"] = c_name
                        if not collection.find_one(q):
                            now = datetime.now(timezone.utc)
                            collection.insert_one({
                                "tenant_id": v_id,
                                "name": c_name,
                                "phone": c_phone or "—",
                                "phone_normalized": c_norm,
                                "email": c_email,
                                "status": "Verified",
                                "bookings": 1,
                                "active": 1 if b.get("status") == "Active" else 0,
                                "paid": float(b.get("paid") or 0),
                                "pending": float(b.get("pending") or 0),
                                "created_at": now,
                                "updated_at": now,
                            })
            except Exception as backfill_exc:
                logger.debug("Customers backfill from bookings: %s", backfill_exc)

        tenant_filter: dict[str, Any] = {"tenant_id": vendor["_id"]}
        if status_filter is not None:
            tenant_filter["status"] = status_filter
        documents = (
            collection.find(tenant_filter)
            .sort([("created_at", DESCENDING), ("_id", DESCENDING)])
            .skip(skip)
            .limit(limit)
        )
        items = [serialize_customer(document) for document in documents]
        total = collection.count_documents(tenant_filter)

        # Single aggregation over non-cancelled, non-deleted bookings to compute fresh dues and total collected
        database = getattr(collection, "database", None)
        if database is not None and items and hasattr(database, "__getitem__"):
            try:
                v_id = vendor["_id"]
                pipeline = [
                    {
                        "$match": {
                            "$and": [
                                {"$or": [
                                    {"tenant_id": str(v_id)},
                                    {"tenant_id": v_id},
                                    {"vendor_id": str(v_id)},
                                    {"vendor_id": v_id},
                                ]},
                                {"status": {"$ne": "Cancelled"}},
                                {"deletedAt": {"$in": [None, False]}},
                            ]
                        }
                    },
                    {
                        "$project": {
                            "cust_id": {"$ifNull": ["$customer_details.id", ""]},
                            "cust_phone": {"$ifNull": ["$customer_details.phone", ""]},
                            "cust_name": {"$ifNull": ["$customer", ""]},
                            "paid": {"$ifNull": ["$paid", 0.0]},
                            "total": {"$ifNull": ["$total_amount", 0.0]},
                        }
                    },
                    {
                        "$group": {
                            "_id": {
                                "id": "$cust_id",
                                "name": "$cust_name",
                                "phone": "$cust_phone",
                            },
                            "total_paid": {"$sum": "$paid"},
                            "total_amount": {"$sum": "$total"},
                        }
                    },
                ]
                agg_results = list(database["bookings"].aggregate(pipeline))
                metrics_by_id: dict[str, dict[str, float]] = {}
                metrics_by_name: dict[str, dict[str, float]] = {}
                metrics_by_phone: dict[str, dict[str, float]] = {}

                for row in agg_results:
                    info = row["_id"]
                    cid = str(info.get("id") or "").strip()
                    cname = str(info.get("name") or "").strip().lower()
                    cphone = normalize_phone(str(info.get("phone") or ""))
                    t_paid = round(float(row.get("total_paid", 0.0)), 2)
                    t_total = round(float(row.get("total_amount", 0.0)), 2)
                    t_pending = max(0.0, round(t_total - t_paid, 2))

                    val = {
                        "paid": t_paid,
                        "pending": t_pending,
                    }
                    if cid:
                        metrics_by_id[cid] = val
                    if cname:
                        metrics_by_name[cname] = val
                    if cphone:
                        metrics_by_phone[cphone] = val

                for item in items:
                    item_id = str(item.get("id", "")).strip()
                    item_name = str(item.get("name", "")).strip().lower()
                    item_phone = normalize_phone(str(item.get("phone", "")))

                    matched = (
                        metrics_by_id.get(item_id)
                        or metrics_by_phone.get(item_phone)
                        or metrics_by_name.get(item_name)
                    )
                    if matched:
                        item["paid"] = matched["paid"]
                        item["pending"] = matched["pending"]
                    else:
                        item["paid"] = 0.0
                        item["pending"] = 0.0
            except Exception as agg_exc:
                logger.debug("Non-fatal booking aggregation for customers: %s", agg_exc)
    except PyMongoError:
        raise_storage_error()
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection[dict[str, Any]], Depends(get_customers_collection)],
) -> dict[str, Any]:
    object_id = parse_customer_id(customer_id)
    try:
        document = collection.find_one({"_id": object_id, "tenant_id": vendor["_id"]})
    except PyMongoError:
        raise_storage_error()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return serialize_customer(document)


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    changes: CustomerUpdate,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection[dict[str, Any]], Depends(get_customers_collection)],
) -> dict[str, Any]:
    object_id = parse_customer_id(customer_id)
    update = changes.model_dump(exclude_unset=True)
    if "email" in update and update["email"] is None:
        update.pop("email")
        unset_email = True
    else:
        unset_email = False
    if "phone" in update:
        update["phone_normalized"] = normalize_phone(update["phone"])
    update["updated_at"] = datetime.now(timezone.utc)

    update_document: dict[str, Any] = {"$set": update}
    if unset_email:
        update_document["$unset"] = {"email": ""}
    try:
        scoped_filter = {"_id": object_id, "tenant_id": vendor["_id"]}
        result = collection.update_one(scoped_filter, update_document)
        if not result.matched_count:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found.",
            )
        document = collection.find_one(scoped_filter)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number or email already exists.",
        ) from exc
    except PyMongoError:
        raise_storage_error()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return serialize_customer(document)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: str,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection[dict[str, Any]], Depends(get_customers_collection)],
) -> None:
    object_id = parse_customer_id(customer_id)
    try:
        result = collection.delete_one({"_id": object_id, "tenant_id": vendor["_id"]})
    except PyMongoError:
        raise_storage_error()
    if not result.deleted_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
