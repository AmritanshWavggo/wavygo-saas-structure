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


def serialize_customer(document: dict[str, Any]) -> dict[str, Any]:
    customer = dict(document)
    customer["id"] = str(customer.pop("_id"))
    return customer


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def raise_storage_error() -> NoReturn:
    logger.exception("Customer database operation failed.")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Customer storage is unavailable.",
    )


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer: CustomerCreate,
    vendor: Annotated[dict[str, Any], Depends(get_current_vendor)],
    collection: Annotated[Collection[dict[str, Any]], Depends(get_customers_collection)],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document: dict[str, Any] = {
        **customer.model_dump(exclude_none=True),
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
