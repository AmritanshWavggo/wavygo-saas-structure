from __future__ import annotations

from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator


class PaymentCreate(BaseModel):
    booking_id: Optional[str] = Field("COUNTER", description="Associated booking ID, e.g. BK-3983")
    customer_name: Optional[str] = Field(None, description="Customer full name")
    amount: float = Field(..., gt=0, description="Payment amount in INR")
    method: str = Field("Cash", description="Payment method: Cash, UPI, Card, Bank Transfer, Net Banking")
    status: Optional[str] = Field("Paid", description="Payment status: Paid, Partial, Pending")
    notes: Optional[str] = Field(None, description="Optional notes or transaction reference")
    transaction_reference: Optional[str] = Field(None, description="UPI reference, UTR, or card last 4 digits")

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "booking" in data and not data.get("booking_id"):
                data["booking_id"] = data["booking"]
            if "customer" in data and not data.get("customer_name"):
                data["customer_name"] = data["customer"]
        return data


class PaymentUpdate(BaseModel):
    status: Optional[str] = Field(None, description="Updated status: Paid, Partial, Refunded")
    notes: Optional[str] = Field(None, description="Updated notes")


class PaymentResponse(BaseModel):
    id: str = Field(..., description="Transaction ID, e.g. TX-7083")
    booking: str
    customer: str
    method: str
    date: str
    amount: float
    status: str = "Paid"
    notes: Optional[str] = None
    transaction_reference: Optional[str] = None
    created_at: str
    updated_at: str


class PaymentStatsResponse(BaseModel):
    total_collected: float
    online_collected: float
    offline_collected: float
    pending_balance: float
    total_transactions: int
