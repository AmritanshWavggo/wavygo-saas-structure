from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator, field_validator


class PaymentCreate(BaseModel):
    booking_id: str = Field(..., min_length=1, description="Associated booking ID, e.g. BK-3983")
    customer_name: Optional[str] = Field(None, description="Customer full name")
    amount: float = Field(..., gt=0, description="Payment amount in INR")
    method: str = Field("Cash", description="Payment method: Cash, UPI, Card, Bank Transfer, Net Banking")
    status: Optional[str] = Field("Paid", description="Payment status: Paid, Partial, Pending")
    notes: Optional[str] = Field(None, description="Optional notes")
    transaction_reference: Optional[str] = Field(None, description="UPI reference, UTR, or card last 4 digits")
    idempotency_key: str = Field(..., min_length=1, description="Unique client UUID for idempotency")
    payment_date: Optional[str] = Field(None, description="Payment date (ISO string or YYYY-MM-DD)")

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "booking" in data and not data.get("booking_id"):
                data["booking_id"] = data["booking"]
            if "customer" in data and not data.get("customer_name"):
                data["customer_name"] = data["customer"]
            if "idempotencyKey" in data and not data.get("idempotency_key"):
                data["idempotency_key"] = data["idempotencyKey"]
            if "transactionReference" in data and not data.get("transaction_reference"):
                data["transaction_reference"] = data["transactionReference"]
            if "paymentDate" in data and not data.get("payment_date"):
                data["payment_date"] = data["paymentDate"]
        return data

    @model_validator(mode="after")
    def validate_non_cash_reference(self) -> PaymentCreate:
        method = (self.method or "Cash").strip().lower()
        ref = (self.transaction_reference or "").strip()
        if method != "cash":
            if not ref:
                raise ValueError(f"Transaction reference is required for {self.method} payments.")
        else:
            if not ref:
                self.transaction_reference = None
        return self

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("idempotency_key is required and cannot be blank.")
        return v

    @field_validator("payment_date")
    @classmethod
    def validate_payment_date(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v_clean = v.strip()
        if not v_clean:
            return None

        # Parse date and verify not in the future (allow 5-minute clock skew)
        try:
            if "T" in v_clean:
                dt = datetime.fromisoformat(v_clean)
            else:
                dt = datetime.strptime(v_clean[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            allowed_max = datetime.now(timezone.utc) + timedelta(minutes=5)
            if dt > allowed_max:
                raise ValueError("Payment date cannot be in the future.")
        except ValueError as exc:
            if "Payment date cannot be in the future" in str(exc):
                raise
            raise ValueError("Invalid payment_date format. Use YYYY-MM-DD or ISO 8601.")
        return v_clean


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
    idempotency_key: Optional[str] = None
    payment_date: Optional[str] = None
    created_at: str
    updated_at: str


class PaymentStatsResponse(BaseModel):
    total_collected: float
    online_collected: float
    offline_collected: float
    pending_balance: float
    total_transactions: int
