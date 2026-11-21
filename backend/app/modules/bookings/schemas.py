from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class VehicleInput(BaseModel):
    vehicle_id: str = Field(..., description="Unique vehicle ID, e.g., VH-1042")
    vehicle_name: str = Field(..., description="Vehicle make and model, e.g., Honda Activa 6G")
    registration: Optional[str] = Field(None, description="Registration number, e.g., GJ 05 AB 4821")
    price_per_day: float = Field(..., ge=0, description="Daily rental price in INR")
    vehicle_type: Optional[str] = Field(None, description="Scooter, Motorcycle, Electric, etc.")


class CustomerInput(BaseModel):
    customer_id: Optional[str] = Field(None, description="Existing customer ID if available, e.g., CU-2048")
    name: str = Field(..., min_length=1, description="Customer full name")
    phone: str = Field(..., min_length=8, description="Contact phone number")
    email: Optional[str] = Field("", description="Customer email address")
    aadhaar: str = Field(..., description="12-digit Aadhaar number")
    driving_licence: Optional[str] = Field(None, description="Driving Licence number")

    @field_validator("aadhaar", mode="before")
    @classmethod
    def validate_aadhaar(cls, value: object) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("Aadhaar Number is required.")
        if not isinstance(value, str):
            raise ValueError("Aadhaar Number must contain exactly 12 numeric digits.")
        value = value.strip()
        if len(value) != 12 or not value.isascii() or not value.isdigit():
            raise ValueError("Aadhaar Number must contain exactly 12 numeric digits.")
        return value


class RentalInput(BaseModel):
    start_date: str = Field(..., description="Pickup date in YYYY-MM-DD")
    end_date: str = Field(..., description="Return date in YYYY-MM-DD")
    pickup_time: str = Field("10:00", description="Pickup time in HH:MM")
    return_time: str = Field("10:00", description="Return time in HH:MM")
    pickup_location: str = Field(..., min_length=1, description="Location of handover/pickup")
    add_ons: bool = Field(False, description="Whether optional add-on kit is included (+500/day)")
    discount: float = Field(0.0, ge=0, description="Discount amount in INR")


class PaymentInput(BaseModel):
    method: str = Field("Cash", description="Payment method: Cash, UPI, Card, Net Banking")
    deposit: bool = Field(False, description="Whether security deposit is taken (+2000)")
    paid_amount: float = Field(0.0, ge=0, description="Initial amount paid at the counter")
    transaction_reference: Optional[str] = Field(None, description="UPI/UTR/Card reference for an advance")


class OfflineBookingCreate(BaseModel):
    vehicle: VehicleInput
    customer: CustomerInput
    rental: RentalInput
    payment: PaymentInput
    notes: Optional[str] = Field(None, description="Optional notes/remarks from counter staff")
    tenant_id: Optional[str] = Field(None, description="Optional tenant/vendor ID")


class OfflineBookingUpdate(BaseModel):
    status: Optional[str] = Field(None, description="Active, Completed, Cancelled")
    pickup_location: Optional[str] = None
    notes: Optional[str] = None


class PaymentRecordCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Payment amount collected in INR")
    method: str = Field("Cash", description="Payment method: Cash, UPI, Card")
    notes: Optional[str] = Field(None, description="Payment note or transaction ID")
    transaction_reference: Optional[str] = Field(None, description="UPI/UTR/Card reference")
    idempotency_key: Optional[str] = Field(None, description="Unique client UUID for idempotency")
    payment_date: Optional[str] = Field(None, description="Payment date")


class LifecycleActionRequest(BaseModel):
    occurred_at: Optional[datetime] = Field(None, description="UTC action time; defaults to server time")
    notes: Optional[str] = Field(None, max_length=1000)


class ReturnBookingRequest(LifecycleActionRequest):
    extra_charges: float = Field(0.0, ge=0)
    extra_charge_reason: Optional[str] = Field(None, max_length=500)


class OfflineBookingResponse(BaseModel):
    id: str = Field(..., description="Booking ID, e.g., BK-123456")
    customer: str
    vehicle: str
    dates: str
    type: str = "Offline"
    status: str
    paid: float
    pending: float
    outstanding: float = 0.0
    payment_status: str = "Unpaid"
    base_amount: float
    add_on_amount: float
    service_fee: float
    discount_amount: float
    deposit_amount: float
    total_amount: float
    rental_days: int
    vehicle_details: dict
    customer_details: dict
    rental_details: dict
    payment_details: dict
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    handoverAt: Optional[str] = None
    returnedAt: Optional[str] = None
    completedAt: Optional[str] = None
    handoverNotes: Optional[str] = None
    returnNotes: Optional[str] = None
    additionalCharges: list[dict] = Field(default_factory=list)
    finalTotalAmount: Optional[float] = None
    finalBill: Optional[dict] = None
    advancePaymentError: Optional[str] = None
