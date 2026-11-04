"""
Customer document model and enums.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class CustomerStatus(str, Enum):
    verified = "Verified"
    review = "Review"


class CustomerModel(BaseModel):
    """
    MongoDB document shape for a customer.
    Customers store only core profile and audit fields.
    Financial and booking aggregations are not stored and return None.
    """

    name: str = ""
    phone: str = ""
    email: Optional[str] = None
    status: CustomerStatus = CustomerStatus.review
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


Customer = CustomerModel

