"""
Vehicle document model.

Pydantic models follow FastAPI / pydantic-settings conventions already in use
in this project (app/core/config.py).  All new fields carry defaults so that
existing MongoDB records that pre-date this schema remain fully readable.

MongoDB index notes (to be applied once a DB-init module is added in Phase 2):
  - vehicles.registration_number: unique sparse index
    (sparse so documents without the field are not rejected)
  collection.create_index(
      [("registration_number", 1)],
      unique=True,
      sparse=True,
      name="uq_registration_number",
  )
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class VehicleType(str, Enum):
    motorcycle = "Motorcycle"
    scooter = "Scooter"
    electric = "Electric"


class FuelType(str, Enum):
    petrol = "Petrol"
    diesel = "Diesel"
    electric = "Electric"


class TransmissionType(str, Enum):
    automatic = "Automatic"
    manual = "Manual"


class RcStatus(str, Enum):
    pending = "Pending review"
    verified = "Verified"


class ListingStatus(str, Enum):
    online = "Online"
    offline = "Offline"


class FleetAvailability(str, Enum):
    """Operational state of a vehicle within the fleet."""

    available = "Available"
    rented = "Rented"
    maintenance = "Maintenance"


class DocumentType(str, Enum):
    rc = "RC"
    insurance = "Insurance"
    puc = "PUC"
    other = "Other"


# ---------------------------------------------------------------------------
# Nested document models
# ---------------------------------------------------------------------------


class PickupLocation(BaseModel):
    """Geographic pickup point for a vehicle."""

    address: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None


class VehiclePhoto(BaseModel):
    """A single photo stored on Cloudinary."""

    url: str
    public_id: str = Field(alias="publicId")

    model_config = {"populate_by_name": True}


class VehicleFile(BaseModel):
    """A compliance document stored on Cloudinary."""

    type: DocumentType
    url: str
    public_id: str = Field(alias="publicId")
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="uploadedAt",
    )
    # Stored so that Cloudinary deletion uses the correct resource_type.
    # PDFs are uploaded with resource_type="raw"; images use "image".
    # Defaults to "image" so legacy records without this field remain valid.
    resource_type: str = Field(default="image", alias="resourceType")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Main Vehicle document model
# ---------------------------------------------------------------------------


class VehicleModel(BaseModel):
    """
    Represents a vehicle document stored in MongoDB.

    Pre-existing fields (from the demo seed) are preserved unchanged.
    All newly added fields have defaults so legacy records remain valid.
    """

    # ------------------------------------------------------------------
    # Pre-existing fields — DO NOT CHANGE defaults or types
    # ------------------------------------------------------------------
    name: str = ""                           # make & model display name
    registration: str = ""                  # human-readable plate (e.g. "GJ 05 AB 4821")
    type: Optional[VehicleType] = None
    fuel: Optional[FuelType] = None
    year: Optional[int] = None
    color: str = ""
    engine_capacity: Optional[int] = Field(default=None, alias="engineCapacity")
    rc_status: RcStatus = Field(default=RcStatus.pending, alias="rcStatus")
    seats: int = 1
    status: ListingStatus = ListingStatus.online
    availability: FleetAvailability = Field(default=FleetAvailability.available, alias="fleetAvailability")  # single source of truth for fleet availability
    price: float = 0.0                       # daily rate in INR
    image: str = ""                          # emoji or URL used by demo UI
    transmission: Optional[TransmissionType] = None

    # ------------------------------------------------------------------
    # NEW fields — all have defaults so legacy records stay valid
    # ------------------------------------------------------------------

    # Listing visibility on WavyGo marketplace
    show_on_wavygo: bool = Field(default=False, alias="showOnWavygo")

    # (fleet_availability removed — availability above is the single source of truth)

    # ------------------------------------------------------------------
    # Pricing & Availability step fields
    # ------------------------------------------------------------------
    daily_rate: float = Field(default=0.0, alias="dailyRate")          # INR / day
    minimum_days: int = Field(default=1, alias="minimumDays")          # minimum booking length
    security_deposit: float = Field(default=0.0, alias="securityDeposit")  # refundable deposit
    pickup_notes: str = Field(default="", alias="pickupNotes")

    # ------------------------------------------------------------------
    # Pickup location
    # ------------------------------------------------------------------
    pickup_location: PickupLocation = Field(
        default_factory=PickupLocation,
        alias="pickupLocation",
    )

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------
    photos: list[VehiclePhoto] = Field(default_factory=list)
    documents: list[VehicleFile] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # RC / registration number (canonical, normalised)
    # Stored as a separate field from `registration` so the sparse unique
    # index can enforce uniqueness without breaking pre-existing records
    # that have no value here.
    # ------------------------------------------------------------------
    registration_number: Optional[str] = Field(
        default=None,
        alias="registrationNumber",
        description=(
            "Normalised RC / registration number (uppercase, trimmed). "
            "Sparse unique index enforced at the database layer. "
            "Existing records without this field are not affected."
        ),
    )

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="updatedAt",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("registration_number", mode="before")
    @classmethod
    def normalise_registration_number(cls, value: Optional[str]) -> Optional[str]:
        """Strip whitespace and uppercase the RC number before storing."""
        if value is None:
            return None
        normalised = value.strip().upper()
        return normalised if normalised else None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Convenience alias used in service / route layers
# ---------------------------------------------------------------------------
Vehicle = VehicleModel
