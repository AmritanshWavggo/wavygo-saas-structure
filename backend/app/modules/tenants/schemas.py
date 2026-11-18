from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RentalRulesSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    minimum_rental_hours: int = Field(default=24, ge=1, le=720, alias="minimumRentalHours")
    advance_booking_days: int = Field(default=90, ge=1, le=365, alias="advanceBookingDays")
    default_security_deposit: float = Field(default=2000.0, ge=0.0, alias="defaultSecurityDeposit")
    cancellation_hours: int = Field(default=24, ge=0, le=168, alias="cancellationHours")
    currency: str = Field(default="INR", max_length=10)


class TenantNotificationSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    booking_notifications: bool = Field(default=True, alias="bookingNotifications")
    payment_notifications: bool = Field(default=True, alias="paymentNotifications")
    maintenance_notifications: bool = Field(default=True, alias="maintenanceNotifications")


class TenantPermissions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    staff_access_level: str = Field(default="Bookings and customers", alias="staffAccessLevel")
    invite_policy: str = Field(default="Owner approval", alias="invitePolicy")


class TenantUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    business_name: Optional[str] = Field(default=None, min_length=1, max_length=120, alias="businessName")
    owner_name: Optional[str] = Field(default=None, max_length=100, alias="ownerName")
    phone: Optional[str] = Field(default=None, max_length=25)
    address: Optional[str] = Field(default=None, max_length=250)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    pincode: Optional[str] = Field(default=None, max_length=20)
    gstin: Optional[str] = Field(default=None, max_length=30)
    rental_rules: Optional[RentalRulesSchema] = Field(default=None, alias="rentalRules")
    notifications: Optional[TenantNotificationSettings] = Field(default=None)
    permissions: Optional[TenantPermissions] = Field(default=None)


class TenantStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(Active|Suspended|Trial|Inactive)$")


class TenantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    business_name: str = Field(alias="businessName")
    owner_name: str = Field(default="", alias="ownerName")
    email: str
    phone: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    pincode: str = ""
    gstin: str = ""
    status: str = "Active"
    plan: str = "Growth"
    rental_rules: RentalRulesSchema = Field(default_factory=RentalRulesSchema, alias="rentalRules")
    notifications: TenantNotificationSettings = Field(default_factory=TenantNotificationSettings)
    permissions: TenantPermissions = Field(default_factory=TenantPermissions)
    created_at: str = Field(default="", alias="createdAt")
    updated_at: str = Field(default="", alias="updatedAt")

