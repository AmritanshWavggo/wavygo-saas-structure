"""
Vehicle payload validation schemas.

Covers all four steps of the Add Vehicle multi-step form:
  Step 0 – Basic Details
  Step 1 – Pricing & Availability
  Step 2 – Documents (metadata only; actual files validated in upload_middleware)
  Step 3 – Review (assembles the full create payload)

Pydantic V2 is used throughout — consistent with the rest of the project
(pydantic-settings already pulls in pydantic >=2).

All schemas use ``model_config = {"populate_by_name": True}`` so that both
camelCase aliases (matching the frontend JSON) and snake_case names work.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.vehicles.models import (
    DocumentType,
    FleetAvailability,
    FuelType,
    RcStatus,
    TransmissionType,
    VehicleType,
)
from app.services.rc_service import normalise_rc, validate_rc_format

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_DAILY_RATE: float = 1.0          # INR
_MAX_DAILY_RATE: float = 1_000_000.0  # INR — sanity upper bound
_MIN_LAT: float = -90.0
_MAX_LAT: float = 90.0
_MIN_LNG: float = -180.0
_MAX_LNG: float = 180.0
_MIN_YEAR: int = 2000
_MAX_YEAR: int = 2030


# ---------------------------------------------------------------------------
# Step 0 — Basic Details
# ---------------------------------------------------------------------------


class BasicDetailsSchema(BaseModel):
    """Validates Step 0: Basic Details."""

    make_model: str = Field(
        ...,
        alias="makeModel",
        min_length=2,
        max_length=120,
        description="Vehicle make and model, e.g. 'Royal Enfield Classic 350'.",
    )
    trim: Optional[str] = Field(default=None, alias="trim", max_length=80)
    registration: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Human-readable plate, e.g. 'GJ 05 AB 4821'.",
    )
    year: int = Field(..., ge=_MIN_YEAR, le=_MAX_YEAR)
    type: VehicleType
    fuel: FuelType
    color: Optional[str] = Field(default=None, max_length=60)
    engine_capacity: Optional[int] = Field(
        default=None,
        alias="engineCapacity",
        ge=0,
        le=10_000,
        description="Engine displacement in cc. Omit for electric vehicles.",
    )
    rc_status: RcStatus = Field(default=RcStatus.pending, alias="rcStatus")
    seats: int = Field(default=1, ge=1, le=10)
    transmission: TransmissionType

    # Canonical RC number (normalised and validated)
    registration_number: Optional[str] = Field(
        default=None,
        alias="registrationNumber",
        description=(
            "Canonical registration number (will be uppercased and stripped). "
            "If omitted, the `registration` field is used as the source."
        ),
    )

    @field_validator("registration_number", mode="before")
    @classmethod
    def normalise_and_validate_rc(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalised = normalise_rc(value)
        if not normalised:
            return None
        if not validate_rc_format(normalised):
            raise ValueError(
                f"'{value}' does not match the expected registration number format "
                "(e.g. GJ05AB4821 or GJ 05 AB 4821)."
            )
        return normalised

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Step 1 — Pricing & Availability
# ---------------------------------------------------------------------------


class PickupLocationSchema(BaseModel):
    """Embedded pickup location sub-schema."""

    address: str = Field(..., min_length=2, max_length=200)
    lat: Optional[float] = Field(default=None, ge=_MIN_LAT, le=_MAX_LAT)
    lng: Optional[float] = Field(default=None, ge=_MIN_LNG, le=_MAX_LNG)

    @model_validator(mode="after")
    def lat_lng_must_be_paired(self) -> "PickupLocationSchema":
        """lat and lng must either both be present or both be absent."""
        has_lat = self.lat is not None
        has_lng = self.lng is not None
        if has_lat != has_lng:
            raise ValueError(
                "Provide both 'lat' and 'lng' together, or omit both."
            )
        return self


class PricingAvailabilitySchema(BaseModel):
    """Validates Step 1: Pricing & Availability."""

    daily_rate: float = Field(
        ...,
        alias="dailyRate",
        ge=_MIN_DAILY_RATE,
        le=_MAX_DAILY_RATE,
        description="Daily rental rate in INR.",
    )
    minimum_days: int = Field(default=1, alias="minimumDays", ge=1, le=365)
    security_deposit: float = Field(
        default=0.0,
        alias="securityDeposit",
        ge=0.0,
        le=_MAX_DAILY_RATE,
        description="Refundable security deposit in INR.",
    )
    pickup_location: PickupLocationSchema = Field(..., alias="pickupLocation")
    pickup_notes: Optional[str] = Field(
        default=None,
        alias="pickupNotes",
        max_length=500,
    )
    show_on_wavygo: bool = Field(default=False, alias="showOnWavygo")
    fleet_availability: FleetAvailability = Field(
        default=FleetAvailability.available,
        alias="fleetAvailability",
    )

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Step 2 — Documents metadata
# ---------------------------------------------------------------------------


class DocumentMetaSchema(BaseModel):
    """
    Metadata for a single document entry.

    The actual file is validated separately in upload_middleware.py.
    This schema covers the metadata that accompanies an already-uploaded file
    (url and publicId come back from Cloudinary after upload).
    """

    type: DocumentType
    url: str = Field(..., min_length=1, description="Cloudinary secure URL.")
    public_id: str = Field(..., alias="publicId", min_length=1)
    uploaded_at: Optional[datetime] = Field(default=None, alias="uploadedAt")

    model_config = {"populate_by_name": True}


class DocumentsSchema(BaseModel):
    """Validates Step 2: Documents."""

    documents: list[DocumentMetaSchema] = Field(default_factory=list)

    @field_validator("documents")
    @classmethod
    def max_documents(cls, value: list[DocumentMetaSchema]) -> list[DocumentMetaSchema]:
        if len(value) > 10:
            raise ValueError("A vehicle may have at most 10 documents.")
        return value


class PhotoMetaSchema(BaseModel):
    """Metadata for a single photo (post-Cloudinary-upload)."""

    url: str = Field(..., min_length=1)
    public_id: str = Field(..., alias="publicId", min_length=1)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Step 3 — Full create/update payload (assembles all steps)
# ---------------------------------------------------------------------------


class VehicleCreateSchema(BasicDetailsSchema, PricingAvailabilitySchema):
    """
    Full vehicle create payload.

    Merges Basic Details + Pricing & Availability.
    Documents and photos are added via separate upload endpoints (Phase 2).

    Inheriting from both step schemas means all validations from each step
    run when this schema is used.
    """

    # Photos and documents may be included if pre-uploaded before submission
    photos: list[PhotoMetaSchema] = Field(default_factory=list)
    documents: list[DocumentMetaSchema] = Field(default_factory=list)

    @field_validator("photos")
    @classmethod
    def max_photos(cls, value: list[PhotoMetaSchema]) -> list[PhotoMetaSchema]:
        if len(value) > 20:
            raise ValueError("A vehicle may have at most 20 photos.")
        return value

    model_config = {"populate_by_name": True}


class VehicleUpdateSchema(BaseModel):
    """
    Partial update payload — all fields optional.

    Used for PATCH requests so that callers only send what changed.
    """

    make_model: Optional[str] = Field(default=None, alias="makeModel", max_length=120)
    trim: Optional[str] = Field(default=None, max_length=80)
    registration: Optional[str] = Field(default=None, max_length=20)
    registration_number: Optional[str] = Field(default=None, alias="registrationNumber")
    year: Optional[int] = Field(default=None, ge=_MIN_YEAR, le=_MAX_YEAR)
    type: Optional[VehicleType] = None
    fuel: Optional[FuelType] = None
    color: Optional[str] = Field(default=None, max_length=60)
    engine_capacity: Optional[int] = Field(default=None, alias="engineCapacity", ge=0, le=10_000)
    rc_status: Optional[RcStatus] = Field(default=None, alias="rcStatus")
    seats: Optional[int] = Field(default=None, ge=1, le=10)
    transmission: Optional[TransmissionType] = None

    daily_rate: Optional[float] = Field(default=None, alias="dailyRate", ge=_MIN_DAILY_RATE, le=_MAX_DAILY_RATE)
    minimum_days: Optional[int] = Field(default=None, alias="minimumDays", ge=1, le=365)
    security_deposit: Optional[float] = Field(default=None, alias="securityDeposit", ge=0.0)
    pickup_location: Optional[PickupLocationSchema] = Field(default=None, alias="pickupLocation")
    pickup_notes: Optional[str] = Field(default=None, alias="pickupNotes", max_length=500)
    show_on_wavygo: Optional[bool] = Field(default=None, alias="showOnWavygo")
    fleet_availability: Optional[FleetAvailability] = Field(default=None, alias="fleetAvailability")

    @field_validator("registration_number", mode="before")
    @classmethod
    def normalise_and_validate_rc(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalised = normalise_rc(value)
        if not normalised:
            return None
        if not validate_rc_format(normalised):
            raise ValueError(
                f"'{value}' does not match the expected registration number format."
            )
        return normalised

    model_config = {"populate_by_name": True}


class ShowOnWavygoSchema(BaseModel):
    """Body accepted by the marketplace visibility toggle endpoint."""

    show_on_wavygo: bool = Field(alias="showOnWavygo")

    model_config = {"populate_by_name": True}
