from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Document display name, e.g. Business registration")
    category: str = Field(..., description="Category: Shop License, GST Certificate, Insurance, PAN Card, RC Book, PUC, Permit")
    scope: str = Field("Business", description="Scope: Business or Vehicle")
    vehicle_id: Optional[str] = Field(None, description="Optional associated vehicle ID (e.g. VH-1042)")
    vehicle_name: Optional[str] = Field(None, description="Optional associated vehicle name (e.g. Honda Activa 6G)")
    status: Optional[str] = Field("In review", description="Status: Verified, In review, Expired, Expires soon")
    notes: Optional[str] = Field(None, description="Optional notes or description")


class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    scope: Optional[str] = None
    vehicle_id: Optional[str] = None
    vehicle_name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str = Field(..., description="Document ID, e.g. DC-101")
    name: str
    category: str
    scope: str
    vehicle_id: Optional[str] = None
    vehicle_name: Optional[str] = None
    file_url: str = Field(..., description="Cloudinary CDN secure URL")
    public_id: Optional[str] = Field(None, description="Cloudinary asset public ID")
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    format: Optional[str] = None
    status: str = "In review"
    date: str
    notes: Optional[str] = None
    created_at: str
    updated_at: str
