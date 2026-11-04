"""
Pydantic schemas for the Customers module.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.customers.models import CustomerStatus

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _reject_control_characters(val: str, field_name: str) -> None:
    if any(ord(c) < 32 or ord(c) == 127 for c in val):
        raise ValueError(f"{field_name} cannot contain control characters.")


def _clean_and_validate_name(val: str) -> str:
    trimmed = val.strip()
    if not trimmed:
        raise ValueError("Name cannot be empty.")
    if len(trimmed) > 100:
        raise ValueError("Name cannot exceed 100 characters.")
    _reject_control_characters(trimmed, "Name")
    return trimmed


def _clean_and_validate_phone(val: str) -> str:
    trimmed = val.strip()
    if not trimmed:
        raise ValueError("Phone number is required.")
    _reject_control_characters(trimmed, "Phone number")

    if trimmed.startswith("+"):
        digits_part = re.sub(r"[\s\-\(\)]", "", trimmed[1:])
        if not digits_part.isdigit() or not (8 <= len(digits_part) <= 15):
            raise ValueError(
                "International phone numbers with a leading '+' must contain between 8 and 15 digits."
            )
        return f"+{digits_part}"
    else:
        digits_only = re.sub(r"[\s\-\(\)]", "", trimmed)
        if re.match(r"^[6-9]\d{9}$", digits_only):
            return f"+91{digits_only}"
        raise ValueError("10-digit Indian phone numbers must start with 6, 7, 8, or 9.")


def _clean_and_validate_email(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    trimmed = val.strip()
    if not trimmed:
        return None
    _reject_control_characters(trimmed, "Email")
    if not _EMAIL_REGEX.match(trimmed):
        raise ValueError("Enter a valid email address.")
    return trimmed.lower()


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=8, max_length=30)
    email: Optional[str] = Field(default=None, max_length=254)
    status: Optional[CustomerStatus] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_and_validate_name(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return _clean_and_validate_phone(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        return _clean_and_validate_email(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        _reject_control_characters(trimmed, "Notes")
        return trimmed


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, min_length=8, max_length=30)
    email: Optional[str] = Field(default=None, max_length=254)
    status: Optional[CustomerStatus] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _clean_and_validate_name(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _clean_and_validate_phone(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        return _clean_and_validate_email(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        _reject_control_characters(trimmed, "Notes")
        return trimmed


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    status: str
    notes: Optional[str] = None
    bookings: Optional[int] = None
    active: Optional[int] = None
    paid: Optional[float] = None
    pending: Optional[float] = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class CustomerMetricsResponse(BaseModel):
    total_customers: int = Field(alias="totalCustomers")
    verified_profiles: int = Field(alias="verifiedProfiles")
    total_collected: Optional[float] = Field(default=None, alias="totalCollected")
    pending_dues: Optional[float] = Field(default=None, alias="pendingDues")

    model_config = ConfigDict(populate_by_name=True)

