"""
Pydantic schemas for the Bookings module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.bookings.models import BookingStatus, CustomerSnapshot, VehicleSnapshot


def _reject_control_characters(val: str, field_name: str) -> None:
    if any(ord(c) < 32 or ord(c) == 127 for c in val):
        raise ValueError(f"{field_name} cannot contain control characters.")


def _validate_tz_aware(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"{field_name} must include a timezone offset (e.g. '2026-11-10T10:00:00Z').")
    return dt.astimezone(timezone.utc)


def _validate_object_id(val: str, field_name: str) -> str:
    trimmed = val.strip()
    if not ObjectId.is_valid(trimmed):
        raise ValueError(f"Invalid {field_name} format.")
    return trimmed


class BookingCreate(BaseModel):
    customer_id: str = Field(..., alias="customerId")
    vehicle_id: str = Field(..., alias="vehicleId")
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    pickup_location: str = Field(..., alias="pickupLocation", min_length=1, max_length=200)
    status: Optional[BookingStatus] = BookingStatus.confirmed
    discount_paise: int = Field(default=0, alias="discountPaise", ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        return _validate_object_id(v, "customerId")

    @field_validator("vehicle_id")
    @classmethod
    def validate_vehicle_id(cls, v: str) -> str:
        return _validate_object_id(v, "vehicleId")

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "startDate")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "endDate")

    @field_validator("pickup_location")
    @classmethod
    def validate_pickup_location(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Pickup location cannot be empty.")
        _reject_control_characters(trimmed, "Pickup location")
        return trimmed

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        _reject_control_characters(trimmed, "Notes")
        return trimmed


class BookingResponse(BaseModel):
    id: str
    booking_number: str = Field(alias="bookingNumber")
    customer_id: str = Field(alias="customerId")
    vehicle_id: str = Field(alias="vehicleId")
    start_date: datetime = Field(alias="startDate")
    end_date: datetime = Field(alias="endDate")
    pickup_location: str = Field(alias="pickupLocation")
    status: str

    currency: str
    daily_rate_paise: int = Field(alias="dailyRatePaise")
    billable_days: int = Field(alias="billableDays")
    base_amount_paise: int = Field(alias="baseAmountPaise")
    discount_paise: int = Field(alias="discountPaise")
    security_deposit_paise: int = Field(alias="securityDepositPaise")
    total_amount_paise: int = Field(alias="totalAmountPaise")

    vehicle_snapshot: VehicleSnapshot = Field(alias="vehicleSnapshot")
    customer_snapshot: CustomerSnapshot = Field(alias="customerSnapshot")
    notes: Optional[str] = None

    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class AvailabilityQuery(BaseModel):
    vehicle_id: str = Field(..., alias="vehicleId")
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    exclude_booking_id: Optional[str] = Field(default=None, alias="excludeBookingId")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("vehicle_id")
    @classmethod
    def validate_vehicle_id(cls, v: str) -> str:
        return _validate_object_id(v, "vehicleId")

    @field_validator("exclude_booking_id")
    @classmethod
    def validate_exclude_booking_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return _validate_object_id(v, "excludeBookingId")

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "startDate")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: datetime) -> datetime:
        return _validate_tz_aware(v, "endDate")

