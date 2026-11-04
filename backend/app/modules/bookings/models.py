"""
Booking document models and enums.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class BookingStatus(str, Enum):
    pending = "Pending"
    confirmed = "Confirmed"
    active = "Active"
    completed = "Completed"
    cancelled = "Cancelled"
    no_show = "No-show"


BLOCKING_STATUSES = frozenset({
    BookingStatus.pending.value,
    BookingStatus.confirmed.value,
    BookingStatus.active.value,
})


class VehicleSnapshot(BaseModel):
    name: str = ""
    registration: str = ""
    registration_number: Optional[str] = Field(default=None, alias="registrationNumber")
    type: Optional[str] = None

    model_config = {"populate_by_name": True}


class CustomerSnapshot(BaseModel):
    name: str = ""
    phone: str = ""
    email: Optional[str] = None

    model_config = {"populate_by_name": True}


class BookingModel(BaseModel):
    booking_number: str = Field(..., alias="bookingNumber")
    customer_id: ObjectId = Field(..., alias="customerId")
    vehicle_id: ObjectId = Field(..., alias="vehicleId")
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    pickup_location: str = Field(..., alias="pickupLocation")
    status: BookingStatus = BookingStatus.confirmed

    currency: str = "INR"
    daily_rate_paise: int = Field(..., alias="dailyRatePaise")
    billable_days: int = Field(..., alias="billableDays")
    base_amount_paise: int = Field(..., alias="baseAmountPaise")
    discount_paise: int = Field(default=0, alias="discountPaise")
    security_deposit_paise: int = Field(default=0, alias="securityDepositPaise")
    total_amount_paise: int = Field(..., alias="totalAmountPaise")

    vehicle_snapshot: VehicleSnapshot = Field(..., alias="vehicleSnapshot")
    customer_snapshot: CustomerSnapshot = Field(..., alias="customerSnapshot")
    notes: Optional[str] = None

    tenant_id: Optional[ObjectId] = Field(default=None, alias="tenantId")
    created_by: Optional[ObjectId] = Field(default=None, alias="createdBy")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="updatedAt",
    )
    deleted_at: Optional[datetime] = Field(default=None, alias="deletedAt")

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


Booking = BookingModel

